#!/usr/bin/env python3
"""
RAMCOIN NODE v9.0.15 - FINAL SECURE VERSION
Полная защита: подписи, форки, орфаны, таймауты
"""

import asyncio, hashlib, json, os, sys, time, array, sqlite3, logging, struct, secrets, zlib, hmac, socket
from typing import Optional, Dict, List, Tuple, Set
from collections import defaultdict, deque, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from aiohttp import web
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

VERSION = "9.0.15"
PROTOCOL = 2
COIN = 100_000_000
MY_WHITE_IP = "90.188.115.169"

DEV_ADDR = "RAM_04a9b30816a61686f377f152435f528e542b61eb7f0c9403778fdd19862600eb18a4faffe64d6a88a8077da4bf5bf908b74f2729c7fe044ddf5528521f5dcbd75a"
BURN_ADDR = "RAM_BURN_" + "0" * 124

DB_PATH = "blockchain_v7.db"
PEERS_DB = "peers_v8.db"
ORPHANS_DB = "orphans.db"

P2P_PORT = 8333
API_PORT = 5000

INITIAL_REWARD = 10 * COIN
BLOCK_TIME = 30.0
HALVING = 876_000
MAX_TARGET = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
INITIAL_TARGET = MAX_TARGET >> 4
MIN_TARGET = MAX_TARGET >> 20
MAX_TIME_DRIFT = 7200
MIN_BLOCK_GAP = 5

SCRATCHPAD_ITER = 8192
BASE_SCRATCHPAD = 524288
MAX_SCRATCHPAD = 4194304

FIXED_FEE = 0.001 * COIN
DEV_SHARE = 10
POOL_FEE = 0.01
BURN_FEE = 0.01
POOL_DIFF_FACTOR = 100

MAX_PEERS = 200
PEER_TIMEOUT = 300
MAX_MEMPOOL = 10000
MAX_BLOCK_TX = 200

CPU_WORKERS = min(8, (os.cpu_count() or 2))
executor = ThreadPoolExecutor(max_workers=CPU_WORKERS)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger('RAMCOIN')


# ==================== PROOF OF WORK ====================
def create_scratchpad_sync(prev_hash, tid, nseed, buffer_size):
    sp = array.array('Q', [0]) * buffer_size
    seed = int(hashlib.sha256(f"{prev_hash}|{tid}|{nseed}|RAMCOIN_v7|{buffer_size}".encode()).hexdigest(), 16)
    s0, s1 = seed, seed ^ 0xDEADBEEF
    for i in range(buffer_size):
        s1, s0 = s0 & 0xFFFFFFFFFFFFFFFF, s1
        s1 ^= (s1 << 23) & 0xFFFFFFFFFFFFFFFF
        s1 ^= (s1 >> 17)
        s1 ^= s0
        s1 ^= (s0 >> 26)
        sp[i] = (s0 + s1) & 0xFFFFFFFFFFFFFFFF
    return sp, seed


def memhard_sync(sp, seed, nonce, nseed, buffer_size):
    sp_copy = array.array('Q', sp)
    mix = seed
    mods = 0
    nseed_current = nseed
    for k in range(SCRATCHPAD_ITER):
        mix = (mix * 0x9E3779B97F4A7C15 + nonce + nseed_current) & 0xFFFFFFFFFFFFFFFF
        mix ^= (mix >> 33)
        mix ^= (mix << 13)
        idx = mix % buffer_size
        rv = sp_copy[idx]
        sp_copy[idx] = (rv ^ mix ^ nonce) & 0xFFFFFFFFFFFFFFFF
        mods += 1
        mix = (mix + rv) & 0xFFFFFFFFFFFFFFFF
        if k % 256 == 0:
            idx2 = ((idx * 1103515245 + 12345) ^ rv) % buffer_size
            sp_copy[idx2] = (sp_copy[idx2] ^ (mix >> 16) ^ nonce) & 0xFFFFFFFFFFFFFFFF
            mods += 1
        if k > 0 and k % 50000 == 0:
            nseed_current = (nseed_current + 1) & 0xFFFFFFFF
            mix = (mix ^ nseed_current) & 0xFFFFFFFFFFFFFFFF
    return mix, nseed_current, mods


def verify_pow_sync(block, target):
    try:
        buffer_size = int(block.get("scratchpad_size", BASE_SCRATCHPAD))
        if buffer_size < BASE_SCRATCHPAD or buffer_size > MAX_SCRATCHPAD:
            return False
        sp, seed = create_scratchpad_sync(str(block["previous_hash"]), int(block.get("extra_nonce", 0)),
                                          int(block.get("nonce_seed", 0)), buffer_size)
        mix, new_nseed, mods = memhard_sync(sp, seed, int(block["nonce"]), int(block.get("nonce_seed", 0)), buffer_size)
        expected = SCRATCHPAD_ITER + (SCRATCHPAD_ITER // 256) + (SCRATCHPAD_ITER // 50000)
        if mods != expected:
            return False
        proof = hashlib.sha256(f"{mix}{block['previous_hash']}{new_nseed}{mods}".encode()).hexdigest()
        return hmac.compare_digest(proof.encode(), block.get("memory_proof", "").encode()) and int(proof, 16) <= target
    except:
        return False


async def verify_pow_async(block, target):
    return await asyncio.get_event_loop().run_in_executor(executor, verify_pow_sync, block, target)


# ==================== БАЗА ПИРОВ ====================
class PeerDB:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(PEERS_DB) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS peers 
                          (addr TEXT PRIMARY KEY, ip TEXT, port INTEGER, height INTEGER, last_seen REAL, is_white INTEGER)''')
            conn.execute('PRAGMA journal_mode=WAL')

    def load_peers(self):
        peers = {}
        try:
            with sqlite3.connect(PEERS_DB) as conn:
                for row in conn.execute(
                        "SELECT addr, ip, port, height, last_seen, is_white FROM peers ORDER BY last_seen DESC LIMIT 500"):
                    addr, ip, port, height, last_seen, is_white = row
                    peers[addr] = {"ip": ip, "port": port, "height": height, "last_seen": last_seen,
                                   "is_white": bool(is_white)}
        except:
            pass
        return peers

    def save_peer(self, addr, info):
        try:
            with sqlite3.connect(PEERS_DB, timeout=10) as conn:
                conn.execute("INSERT OR REPLACE INTO peers VALUES (?,?,?,?,?,?)",
                             (addr, info.get("ip", ""), info.get("port", P2P_PORT),
                              info.get("height", 0), info.get("last_seen", time.time()),
                              1 if info.get("is_white", False) else 0))
        except:
            pass

    def cleanup(self, max_age=86400):
        try:
            cutoff = time.time() - max_age
            with sqlite3.connect(PEERS_DB, timeout=10) as conn:
                conn.execute("DELETE FROM peers WHERE last_seen < ?", (cutoff,))
        except:
            pass


# ==================== P2P ====================
class PeerManager:
    def __init__(self, bc=None):
        self.bc = bc
        self.peers = {}
        self.white_peers = {}
        self.grey_peers = {}
        self.banned = {}
        self.scores = defaultdict(int)
        self.connections = {}
        self.server = None
        self.running = False
        self.syncing = False
        self.peer_db = PeerDB()
        self.my_ip = MY_WHITE_IP
        self.is_white = True

        saved = self.peer_db.load_peers()
        for addr, info in saved.items():
            if info.get("is_white", False):
                self.white_peers[addr] = info
            else:
                self.grey_peers[addr] = info
            self.peers[addr] = info
        log.info(f"Загружено пиров: {len(self.white_peers)} белых, {len(self.grey_peers)} серых")

    def is_peer_white(self, ip):
        try:
            parts = list(map(int, ip.split('.')))
            ip_num = (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
            for start, end in [("10.0.0.0", "10.255.255.255"), ("172.16.0.0", "172.31.255.255"),
                               ("192.168.0.0", "192.168.255.255"), ("127.0.0.0", "127.255.255.255")]:
                s = list(map(int, start.split('.')))
                e = list(map(int, end.split('.')))
                if (s[0] << 24) + (s[1] << 16) + (s[2] << 8) + s[3] <= ip_num <= (e[0] << 24) + (e[1] << 16) + (
                        e[2] << 8) + e[3]:
                    return False
            return True
        except:
            return False

    async def start_server(self, host, port):
        try:
            self.server = await asyncio.start_server(self._handle, host, port)
            self.running = True
            log.info(f"P2P сервер: {host}:{port} (Белый IP: {self.is_white})")
            for addr, info in list(self.white_peers.items()):
                ip = info.get("ip", addr.split(":")[0])
                p = info.get("port", P2P_PORT)
                if ip != self.my_ip:
                    asyncio.create_task(self._connect_to_peer(ip, p))
            asyncio.create_task(self._peer_discovery_loop())
        except Exception as e:
            log.error(f"Ошибка P2P сервера: {e}")

    async def _handle(self, r, w):
        addr = f"{r.get_extra_info('peername')[0]}:{r.get_extra_info('peername')[1]}"
        ip = r.get_extra_info('peername')[0]
        if addr in self.banned:
            if time.time() < self.banned[addr]:
                w.close()
                return
            del self.banned[addr]
        self.connections[addr] = w
        try:
            await self._send(w, {"type": "hello", "version": VERSION, "height": self.bc.height if self.bc else 0,
                                 "ip": self.my_ip, "port": P2P_PORT, "is_white": self.is_white})
            while self.running:
                ld = await asyncio.wait_for(r.read(4), timeout=PEER_TIMEOUT)
                if not ld: break
                l = struct.unpack('>I', ld)[0]
                if l > 10 * 1024 * 1024: self.penalize(addr); break
                d = await asyncio.wait_for(r.read(l), timeout=30)
                try:
                    d = zlib.decompress(d)
                except:
                    pass
                msg = json.loads(d.decode())
                resp = await self._proc(msg, addr, w)
                if resp: await self._send(w, resp)
        except:
            pass
        finally:
            self.connections.pop(addr, None)
            try:
                w.close()
            except:
                pass

    async def _send(self, w, m):
        d = zlib.compress(json.dumps(m).encode())
        w.write(struct.pack('>I', len(d)))
        w.write(d)
        await w.drain()

    async def _proc(self, m, addr, writer):
        t = m.get("type")
        if t == "hello":
            peer_height = m.get("height", 0)
            peer_ip = m.get("ip", addr.split(":")[0])
            peer_port = m.get("port", P2P_PORT)
            peer_is_white = m.get("is_white", False)
            info = {"last_seen": time.time(), "height": peer_height, "ip": peer_ip, "port": peer_port,
                    "is_white": peer_is_white}
            if peer_is_white:
                self.white_peers[addr] = info
                if self.bc and peer_height > self.bc.height and not self.syncing:
                    asyncio.create_task(self._sync_from_peer(addr, writer))
            else:
                self.grey_peers[addr] = info
            self.peers[addr] = info
            self.peer_db.save_peer(addr, info)
            return {"type": "hello_ack", "version": VERSION, "height": self.bc.height if self.bc else 0,
                    "is_white": self.is_white}
        elif t == "get_blocks":
            s = m.get("start_height", 0)
            l = min(m.get("limit", 500), 500)
            if self.bc and 0 <= s < len(self.bc.chain):
                blocks = [self.bc.chain[i] for i in range(s, min(s + l, len(self.bc.chain)))]
                return {"type": "blocks", "blocks": blocks, "start_height": s, "total_height": self.bc.height}
            return {"type": "blocks", "blocks": [], "start_height": s, "total_height": self.bc.height if self.bc else 0}
        elif t == "blocks":
            if self.bc:
                for b in m.get("blocks", []):
                    if b.get("index") == self.bc.height:
                        await self.bc.add_block(b, addr)
        elif t == "new_block":
            if self.bc and m.get("block", {}).get("index") == self.bc.height:
                await self.bc.add_block(m["block"], addr)
        elif t == "get_peers":
            return {"type": "peers",
                    "peers": [{"ip": wi.get("ip", ""), "port": wi.get("port", P2P_PORT), "height": wi.get("height", 0)}
                              for wi in list(self.white_peers.values())[:100]]}
        elif t == "peers":
            for p in m.get("peers", []):
                p_addr = f"{p.get('ip', '')}:{p.get('port', P2P_PORT)}"
                if p.get('ip') and p.get('ip') != self.my_ip and p_addr not in self.peers:
                    if self.is_peer_white(p['ip']):
                        info = {"last_seen": time.time(), "height": p.get("height", 0), "ip": p['ip'],
                                "port": p.get("port", P2P_PORT), "is_white": True}
                        self.white_peers[p_addr] = self.peers[p_addr] = info
                        self.peer_db.save_peer(p_addr, info)
                        asyncio.create_task(self._connect_to_peer(p['ip'], p.get("port", P2P_PORT)))
        elif t == "ping":
            return {"type": "pong", "height": self.bc.height if self.bc else 0}
        return None

    async def _connect_to_peer(self, ip, port):
        addr = f"{ip}:{port}"
        if ip == self.my_ip or addr in self.connections: return
        try:
            r, w = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=10)
            self.connections[addr] = w
            await self._send(w, {"type": "hello", "version": VERSION, "height": self.bc.height if self.bc else 0,
                                 "ip": self.my_ip, "port": P2P_PORT, "is_white": self.is_white})
            log.info(f"Подключены к {addr}")
        except:
            pass

    async def _sync_from_peer(self, addr, writer):
        if self.syncing: return
        self.syncing = True
        try:
            await self._send(writer, {"type": "get_blocks", "start_height": self.bc.height, "limit": 500})
            for _ in range(30):
                await asyncio.sleep(1)
                if self.bc.height >= self.peers.get(addr, {}).get("height", 0): break
        finally:
            self.syncing = False

    async def _peer_discovery_loop(self):
        await asyncio.sleep(30)
        while self.running:
            for writer in list(self.connections.values()):
                try:
                    await self._send(writer, {"type": "get_peers"})
                except:
                    pass
            await asyncio.sleep(120)

    async def broadcast_block(self, b):
        await self._bcast({"type": "new_block", "block": b})

    async def _bcast(self, m):
        dead = []
        for a, w in list(self.connections.items()):
            try:
                d = zlib.compress(json.dumps(m).encode())
                w.write(struct.pack('>I', len(d)))
                w.write(d)
                await w.drain()
            except:
                dead.append(a)
        for a in dead: self.connections.pop(a, None)

    def penalize(self, a):
        self.scores[a] += 1
        if self.scores[a] >= 5:
            self.banned[a] = time.time() + 3600

    async def stop(self):
        self.running = False
        for w in self.connections.values():
            try:
                w.close()
            except:
                pass
        if self.server:
            self.server.close()
            await self.server.wait_closed()


# ==================== БЛОКЧЕЙН С ПОЛНОЙ ЗАЩИТОЙ ====================
class Blockchain:
    def __init__(self, p2p=None):
        self.p2p = p2p
        self.lock = asyncio.Lock()
        self.share_lock = asyncio.Lock()
        self.fork_lock = asyncio.Lock()
        self.chain = []
        self.height = 0
        self.accounts = {DEV_ADDR: 100 * COIN}
        self.nonces = {DEV_ADDR: 0}
        self.target = INITIAL_TARGET
        self.total_tx = 0
        self.accepted = 0
        self.rejected = 0
        self.start_time = time.time()
        self.last_block_time = 0
        self.mempool = deque(maxlen=MAX_MEMPOOL)
        self.mempool_hashes = set()
        self.pool_shares = defaultdict(int)
        self.pool_total = 0
        self.pool_template = None
        self.pool_template_ts = 0
        self.ws_clients = set()
        self.orphans = {}  # 🔥 Хранилище орфанных блоков
        self.fork_chain = []  # 🔥 Альтернативная цепь при форке
        self._init_db()
        if not self._load():
            self._create_genesis()
        log.info(f"RAMCOIN v{VERSION} | H:{self.height} | D:{self.fmt_diff()} | Аккаунтов: {len(self.accounts)}")

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS blocks (idx INTEGER PRIMARY KEY, data TEXT, hash TEXT UNIQUE)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, val TEXT)''')
            conn.execute('PRAGMA journal_mode=WAL')
        with sqlite3.connect(ORPHANS_DB) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS orphans (idx INTEGER, data TEXT, hash TEXT, received REAL)''')
            conn.execute('PRAGMA journal_mode=WAL')

    def _load(self):
        try:
            if not os.path.exists(DB_PATH): return False
            with sqlite3.connect(DB_PATH) as conn:
                for key in ['height', 'accounts', 'nonces', 'target', 'total_tx', 'accepted', 'rejected']:
                    if not conn.execute("SELECT val FROM state WHERE key=?", (key,)).fetchone(): return False
                self.height = int(conn.execute("SELECT val FROM state WHERE key='height'").fetchone()[0])
                self.accounts = json.loads(conn.execute("SELECT val FROM state WHERE key='accounts'").fetchone()[0])
                self.nonces = json.loads(conn.execute("SELECT val FROM state WHERE key='nonces'").fetchone()[0])
                self.target = int(conn.execute("SELECT val FROM state WHERE key='target'").fetchone()[0])
                self.total_tx = int(conn.execute("SELECT val FROM state WHERE key='total_tx'").fetchone()[0])
                self.accepted = int(conn.execute("SELECT val FROM state WHERE key='accepted'").fetchone()[0])
                self.rejected = int(conn.execute("SELECT val FROM state WHERE key='rejected'").fetchone()[0])
                rows = conn.execute("SELECT data FROM blocks ORDER BY idx").fetchall()
                self.chain = [json.loads(r[0]) for r in rows]
                self.height = len(self.chain)
                # Проверка целостности цепи
                for i in range(1, len(self.chain)):
                    if self.chain[i]["previous_hash"] != self.chain[i - 1]["hash"]:
                        log.error(f"ЦЕПЬ РВАНАЯ на блоке {i}!")
                        return False
                log.info(f"✅ БЛОКЧЕЙН ЗАГРУЖЕН: {self.height} блоков")
                return True
        except Exception as e:
            log.error(f"Ошибка загрузки: {e}")
            return False

    def _create_genesis(self):
        g = {"index": 0, "previous_hash": "0" * 64, "transactions": [], "timestamp": int(time.time() - BLOCK_TIME),
             "nonce": 0, "nonce_seed": 0, "memory_proof": "0" * 64, "target": self.target,
             "miner_payout_address": DEV_ADDR, "miner_signature": "0" * 128, "extra_nonce": 0,
             "scratchpad_mods": 0, "scratchpad_size": BASE_SCRATCHPAD, "version": PROTOCOL}
        g["hash"] = self.calc_hash(g)
        self._save_block(g)
        self.chain.append(g)
        self.height = 1
        self.last_block_time = g["timestamp"]
        self.accepted = 1

    def _save_block(self, block):
        try:
            with sqlite3.connect(DB_PATH, timeout=30) as conn:
                conn.execute("INSERT OR REPLACE INTO blocks VALUES (?,?,?)",
                             (block['index'], json.dumps(block), block['hash']))
                for key, val in [('height', str(self.height)), ('accounts', json.dumps(self.accounts)),
                                 ('nonces', json.dumps(self.nonces)), ('target', str(self.target)),
                                 ('total_tx', str(self.total_tx)), ('accepted', str(self.accepted)),
                                 ('rejected', str(self.rejected))]:
                    conn.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, val))
                conn.commit()
        except Exception as e:
            log.error(f"Ошибка сохранения: {e}")

    def _save_orphan(self, block):
        """Сохраняет орфанный блок"""
        try:
            with sqlite3.connect(ORPHANS_DB, timeout=10) as conn:
                conn.execute("INSERT OR REPLACE INTO orphans VALUES (?,?,?,?)",
                             (block['index'], json.dumps(block), block['hash'], time.time()))
                conn.commit()
            self.orphans[block['index']] = block
            log.info(f"Орфанный блок #{block['index']} сохранён")
        except:
            pass

    def _check_orphans(self):
        """Проверяет не появился ли родитель для орфанов"""
        if not self.chain:
            return
        last_hash = self.chain[-1]["hash"]
        next_idx = self.height

        if next_idx in self.orphans:
            orphan = self.orphans[next_idx]
            if orphan["previous_hash"] == last_hash:
                log.info(f"Найден родитель для орфана #{next_idx}")
                return orphan
        return None

    def calc_hash(self, block):
        c = block.copy()
        c.pop("hash", None)
        c.pop("miner_signature", None)
        return hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()

    def fmt_diff(self):
        if self.target == 0: return "∞"
        sd = MAX_TARGET / self.target
        if sd >= 1e9: return f"{sd / 1e9:.2f} GRam/s"
        if sd >= 1e6: return f"{sd / 1e6:.2f} MRam/s"
        return f"{sd / 1e3:.2f} KRam/s" if sd >= 1e3 else f"{sd:.2f} Ram/s"

    def _adjust_target(self):
        """Плавный перерасчёт сложности каждый блок"""
        if self.height < 2:
            return

        # Время между последними двумя блоками
        actual_time = self.chain[-1]["timestamp"] - self.chain[-2]["timestamp"]
        actual_time = max(MIN_BLOCK_GAP, min(actual_time, BLOCK_TIME * 20))  # От 5 сек до 10 мин

        # Во сколько раз отклонились от цели
        ratio = BLOCK_TIME / actual_time

        # 🔥 ПЛАВНО: максимум 5% изменения за блок
        ratio = max(0.95, min(1.05, ratio))

        # Новый target
        new_target = int(self.target * ratio)

        # Границы (не слишком легко, не слишком сложно)
        new_target = max(MIN_TARGET, min(INITIAL_TARGET, new_target))

        self.target = new_target

    def reward_at(self, h):
        x = h // HALVING
        return 0 if x >= 64 else INITIAL_REWARD >> x

    # 🔒 ПРОВЕРКА ПОДПИСИ БЛОКА
    def verify_block_signature(self, block: dict) -> bool:
        """Проверяет что блок подписан владельцем адреса"""
        if block.get("pool_block", False):
            return True  # Пулы блоки без подписи

        miner_address = block.get("miner_payout_address", "")
        if not miner_address.startswith("RAM_"):
            return False

        signature_hex = block.get("miner_signature", "")
        if not signature_hex or signature_hex == "0" * 128:
            return False

        try:
            # Извлекаем публичный ключ из адреса
            pub_hex = miner_address[4:]  # Убираем "RAM_"
            pub_bytes = bytes.fromhex(pub_hex)
            pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub_bytes)

            # Данные которые подписывал майнер (как в майнере)
            data = OrderedDict([
                ("v", PROTOCOL), ("i", block["index"]), ("ph", block["previous_hash"]),
                ("t", block["timestamp"]), ("n", block["nonce"]),
                ("ns", block.get("nonce_seed", 0)), ("mp", block["memory_proof"]),
                ("ma", miner_address), ("sm", block.get("scratchpad_mods", 0)),
                ("ss", block.get("scratchpad_size", BASE_SCRATCHPAD)),
                ("en", block.get("extra_nonce", 0))
            ])

            hash_bytes = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).digest()
            signature = bytes.fromhex(signature_hex)
            pub_key.verify(signature, hash_bytes, ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            log.warning(f"Невалидная подпись блока #{block.get('index')}")
            return False
        except Exception as e:
            log.error(f"Ошибка проверки подписи: {e}")
            return False

    # 🔒 ПРОВЕРКА ПОДПИСИ ТРАНЗАКЦИИ
    def verify_tx_signature(self, tx: dict) -> bool:
        """Проверяет что транзакция подписана отправителем"""
        try:
            sender = tx.get("sender", "")
            if not sender.startswith("RAM_"):
                return False

            pub_hex = sender[4:]
            pub_bytes = bytes.fromhex(pub_hex)
            pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub_bytes)

            # Данные которые подписывал отправитель
            signing_data = {
                "sender": tx["sender"],
                "recipient": tx["recipient"],
                "amount": tx["amount"],
                "fee": tx.get("fee", FIXED_FEE),
                "nonce": tx["nonce"],
                "timestamp": tx["timestamp"]
            }

            hash_bytes = json.dumps(signing_data, sort_keys=True).encode()
            signature = bytes.fromhex(tx.get("signature", ""))
            pub_key.verify(signature, hash_bytes, ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            return False
        except Exception:
            return False

    # 🔒 ЗАЩИТА ОТ ФОРКОВ
    async def resolve_fork(self, alt_chain: list) -> bool:
        """Разрешает форк - выбирает самую длинную валидную цепь"""
        async with self.fork_lock:
            if len(alt_chain) <= len(self.chain):
                return False

            # Проверяем валидность альтернативной цепи
            for i in range(1, len(alt_chain)):
                if alt_chain[i]["previous_hash"] != alt_chain[i - 1]["hash"]:
                    return False
                if not verify_pow_sync(alt_chain[i], alt_chain[i].get("target", self.target)):
                    return False

            # Находим точку расхождения
            fork_point = 0
            for i in range(min(len(self.chain), len(alt_chain))):
                if self.chain[i]["hash"] != alt_chain[i]["hash"]:
                    fork_point = i
                    break

            if fork_point == 0:
                return False

            log.warning(f"ФОРК! Точка расхождения: блок #{fork_point}")
            log.warning(f"Наша цепь: {len(self.chain)} блоков, Альтернативная: {len(alt_chain)} блоков")

            # Откатываем до точки форка
            old_chain = self.chain[fork_point:]
            self.chain = self.chain[:fork_point]

            # Восстанавливаем состояние на точке форка
            self._rebuild_state()

            # Применяем новую цепь
            for block in alt_chain[fork_point:]:
                success, _ = await self.add_block(block, "fork")
                if not success:
                    # Восстанавливаем старую цепь
                    self.chain = self.chain[:fork_point] + old_chain
                    self._rebuild_state()
                    return False

            log.info(f"Форк разрешён. Новая высота: {self.height}")
            return True

    def _rebuild_state(self):
        """Перестраивает состояние из цепи"""
        self.accounts = {DEV_ADDR: 100 * COIN}
        self.nonces = {DEV_ADDR: 0}
        self.total_tx = 0

        for block in self.chain:
            if block["index"] == 0:
                continue

            miner = block.get("miner_payout_address", "")
            is_pool = block.get("pool_block", False)
            reward = 0

            if not is_pool:
                reward = self.reward_at(block["index"])
                self.accounts[miner] = self.accounts.get(miner, 0) + reward

            for tx in block.get("transactions", []):
                s, r, a = tx["sender"], tx["recipient"], int(tx["amount"])
                fee = int(tx.get("fee", FIXED_FEE))
                if self.accounts.get(s, 0) >= a + fee:
                    self.accounts[s] = self.accounts.get(s, 0) - (a + fee)
                    self.accounts[r] = self.accounts.get(r, 0) + a
                    self.nonces[s] = self.nonces.get(s, 0) + 1
                    self.total_tx += 1

    async def add_block(self, block, source="unknown"):
        async with self.lock:
            idx = int(block.get("index", -1))

            # 🔥 Проверка орфанов
            if idx > self.height:
                log.info(f"Орфанный блок #{idx} (мы на {self.height})")
                self._save_orphan(block)
                return False, "orphan_future"

            if idx < self.height:
                # Блок для уже пройденной высоты - возможный форк
                if idx == self.height - 1 and block["previous_hash"] != self.chain[-1]["hash"]:
                    log.warning(f"Возможный форк на высоте {idx}")
                    self.rejected += 1
                    return False, "fork_detected"
                self.rejected += 1
                return False, f"idx {idx} < {self.height}"

            if idx != self.height:
                self.rejected += 1
                return False, f"idx {idx} != {self.height}"

            if self.chain and self.chain[-1]["hash"] != block.get("previous_hash"):
                self.rejected += 1
                return False, "prev_hash"

            if int(block.get("timestamp", 0)) > time.time() + MAX_TIME_DRIFT:
                self.rejected += 1
                return False, "future"

            # 🔒 Проверка PoW
            if not await verify_pow_async(block, self.target):
                self.rejected += 1
                return False, "pow"

            # 🔒 Проверка подписи блока
            if not self.verify_block_signature(block):
                self.rejected += 1
                return False, "block_signature"

            # 🔒 Проверка подписей транзакций
            for tx in block.get("transactions", []):
                if not self.verify_tx_signature(tx):
                    self.rejected += 1
                    log.warning(f"Невалидная подпись транзакции в блоке #{idx}")
                    return False, "tx_signature"

            miner = block.get("miner_payout_address", "")
            is_pool = block.get("pool_block", False)
            reward = 0

            if is_pool:
                if self.pool_total > 0:
                    rw = self.reward_at(idx)
                    df, bn = int(rw * POOL_FEE), int(rw * BURN_FEE)
                    ms = rw - df - bn
                    self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + df
                    self.accounts[BURN_ADDR] = self.accounts.get(BURN_ADDR, 0) + bn
                    for a, s in list(self.pool_shares.items()):
                        if s > 0:
                            p = int(ms * s / self.pool_total)
                            if p > 0: self.accounts[a] = self.accounts.get(a, 0) + p
                    self.pool_shares.clear()
                    self.pool_total = 0
            else:
                reward = self.reward_at(idx)
                self.accounts[miner] = self.accounts.get(miner, 0) + reward

            for tx in block.get("transactions", []):
                s, r, a = tx["sender"], tx["recipient"], int(tx["amount"])
                fee = int(tx.get("fee", FIXED_FEE))
                if self.accounts.get(s, 0) < a + fee:
                    continue
                df = (fee * DEV_SHARE) // 100
                mf = fee - df
                self.accounts[s] = self.accounts.get(s, 0) - (a + fee)
                self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + df
                self.accounts[miner] = self.accounts.get(miner, 0) + mf
                self.accounts[r] = self.accounts.get(r, 0) + a
                self.nonces[s] = self.nonces.get(s, 0) + 1
                self.total_tx += 1

            self._adjust_target()
            block["target"] = self.target
            block["hash"] = self.calc_hash(block)
            self._save_block(block)
            self.chain.append(block)
            self.height += 1
            self.last_block_time = block["timestamp"]
            self.accepted += 1

            # 🔥 Проверяем орфаны после добавления блока
            orphan = self._check_orphans()
            if orphan:
                log.info(f"Применяем орфанный блок #{orphan['index']}")
                asyncio.create_task(self.add_block(orphan, "orphan"))

            asyncio.create_task(self._notify(block))
            if self.p2p:
                asyncio.create_task(self.p2p.broadcast_block(block))

            log.info(f"#{idx} | {'POOL' if is_pool else 'SOLO'} | +{reward / COIN:.2f} RAM | H:{self.height}")
            return True, "ok"

    async def submit_share(self, addr, nonce, nseed, mix, mods, extra, size):
        async with self.share_lock:
            if not self.chain:
                return False
            prev_hash = self.get_pool_template()["previous_hash"]
            proof = hashlib.sha256(f"{mix}{prev_hash}{nseed}{mods}".encode()).hexdigest()
            proof_int = int(proof, 16)
            pool_target = min(MAX_TARGET, int(self.target * POOL_DIFF_FACTOR))

            if proof_int <= self.target:
                block = {"index": self.height, "previous_hash": prev_hash, "timestamp": int(time.time()),
                         "nonce": nonce, "nonce_seed": nseed, "memory_proof": proof, "target": self.target,
                         "extra_nonce": extra, "miner_payout_address": addr, "scratchpad_mods": mods,
                         "scratchpad_size": size, "pool_block": True, "transactions": list(self.mempool)[:MAX_BLOCK_TX],
                         "version": PROTOCOL, "miner_signature": ""}
                if verify_pow_sync(block, self.target):
                    return (await self.add_block(block, "pool"))[0]
                return False
            elif proof_int <= pool_target:
                self.pool_shares[addr] = self.pool_shares.get(addr, 0) + 1
                self.pool_total += 1
                return True
            return False

    def get_pool_template(self):
        now = time.time()
        if self.pool_template and (now - self.pool_template_ts) < 1.0:
            return self.pool_template
        if not self.chain:
            return None
        self.pool_template = {"height": self.height, "previous_hash": self.chain[-1]["hash"],
                              "target": self.target,
                              "pool_target": min(MAX_TARGET, int(self.target * POOL_DIFF_FACTOR)),
                              "transactions": list(self.mempool)[:100], "timestamp": int(now)}
        self.pool_template_ts = now
        return self.pool_template

    async def _notify(self, block):
        msg = json.dumps({"event": "new_block", "height": self.height, "hash": block["hash"], "target": self.target})
        dead = set()
        for ws in list(self.ws_clients):
            try:
                if not ws.closed:
                    await ws.send_str(msg)
            except:
                dead.add(ws)
        self.ws_clients -= dead

    def get_stats(self):
        return {"version": VERSION, "height": self.height, "difficulty": self.fmt_diff(),
                "total_supply": sum(self.accounts.values()) / COIN, "accounts": len(self.accounts),
                "peers": len(self.p2p.connections) if self.p2p else 0, "miners": len(self.ws_clients),
                "mempool": len(self.mempool), "transactions": self.total_tx, "blocks": self.accepted,
                "uptime": int(time.time() - self.start_time), "reward": self.reward_at(self.height) / COIN,
                "pool": {"shares": self.pool_total, "miners": len(self.pool_shares)},
                "burn": self.accounts.get(BURN_ADDR, 0) / COIN, "current_target": self.target,
                "chain": self.chain[-10:], "length": self.height}

    def get_address(self, addr):
        if not addr.startswith("RAM_"):
            return None
        return {"address": addr, "balance": self.accounts.get(addr, 0) / COIN, "nonce": self.nonces.get(addr, 0)}


# ==================== API ====================
async def handle_chain(request):
    return web.json_response(request.app['bc'].get_stats())


async def handle_stats(request):
    return web.json_response(request.app['bc'].get_stats())


async def handle_health(request):
    bc = request.app['bc']
    return web.json_response(
        {"ok": True, "version": VERSION, "height": bc.height, "uptime": int(time.time() - bc.start_time)})


async def handle_block(request):
    bc = request.app['bc']
    try:
        i = int(request.match_info['idx'])
        if 0 <= i < len(bc.chain):
            return web.json_response(bc.chain[i])
    except:
        pass
    return web.json_response({"error": "not found"}, status=404)


async def handle_address(request):
    bc = request.app['bc']
    d = bc.get_address(request.match_info['addr'])
    return web.json_response(d) if d else web.json_response({"error": "invalid"}, status=400)


async def handle_pending(request):
    return web.json_response(list(request.app['bc'].mempool))


async def handle_top(request):
    bc = request.app['bc']
    lim = min(int(request.query.get("limit", 10)), 100)
    return web.json_response([{"address": a, "balance": b / COIN} for a, b in
                              sorted(bc.accounts.items(), key=lambda x: x[1], reverse=True)[:lim]])


async def handle_mine(request):
    bc = request.app['bc']
    try:
        d = await request.json()
    except:
        return web.json_response({"status": "rejected"}, status=400)
    ok, why = await bc.add_block(d, request.remote)
    return web.json_response({"status": "ok" if ok else "rejected", "reason": why})


async def handle_tx(request):
    bc = request.app['bc']
    try:
        d = await request.json()
    except:
        return web.json_response({"status": "error"}, status=400)
    # Проверяем подпись транзакции
    if not bc.verify_tx_signature(d):
        return web.json_response({"status": "rejected", "reason": "invalid signature"}, status=400)
    bc.mempool.append(d)
    bc.mempool_hashes.add(d.get("signature", ""))
    return web.json_response({"status": "ok"})


async def handle_pool_tmpl(request):
    bc = request.app['bc']
    t = bc.get_pool_template()
    return web.json_response(t) if t else web.json_response({"error": "no chain"}, status=503)


async def handle_pool_share(request):
    bc = request.app['bc']
    try:
        d = await request.json()
    except:
        return web.json_response({"status": "rejected"}, status=400)
    a = d.get("miner_address", "")
    if not a.startswith("RAM_"):
        return web.json_response({"status": "rejected"}, status=400)
    ok = await bc.submit_share(a, int(d.get("nonce", 0)), int(d.get("nonce_seed", 0)),
                               d.get("mix", "0"), int(d.get("mods", 0)),
                               int(d.get("extra_nonce", 0)), int(d.get("scratchpad_size", BASE_SCRATCHPAD)))
    return web.json_response({"status": "ok" if ok else "rejected"})


async def handle_pool_stats(request):
    bc = request.app['bc']
    return web.json_response({"shares": bc.pool_total, "miners": len(bc.pool_shares)})


async def handle_ws(request):
    bc = request.app['bc']
    ws = web.WebSocketResponse(heartbeat=30, timeout=60)
    await ws.prepare(request)
    bc.ws_clients.add(ws)
    log.info(f"WS клиент подключился (всего: {len(bc.ws_clients)})")
    try:
        await ws.send_json({"event": "connected", "height": bc.height, "target": bc.target, "version": VERSION})
        async for m in ws:
            if m.type in (web.WSMsgType.CLOSE, web.WSMsgType.ERROR):
                break
    except:
        pass
    finally:
        bc.ws_clients.discard(ws)
    return ws


class Node:
    def __init__(self):
        self.p2p = PeerManager()
        self.bc = Blockchain(self.p2p)
        self.p2p.bc = self.bc
        self.running = False

    async def start(self):
        self.running = True
        app = web.Application(client_max_size=10 * 1024 * 1024)
        app['bc'] = self.bc

        # 🔥 CORS MIDDLEWARE
        @web.middleware
        async def cors_middleware(request, handler):
            if request.method == "OPTIONS":
                resp = web.Response(status=204)
            else:
                resp = await handler(request)
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return resp

        app.middlewares.append(cors_middleware)

        # Роуты
        app.router.add_get('/chain', handle_chain)
        app.router.add_get('/stats', handle_stats)
        app.router.add_get('/health', handle_health)
        app.router.add_get('/block/{idx}', handle_block)
        app.router.add_get('/address/{addr}', handle_address)
        app.router.add_get('/pending', handle_pending)
        app.router.add_get('/top', handle_top)
        app.router.add_post('/mine', handle_mine)
        app.router.add_post('/tx', handle_tx)
        app.router.add_get('/pool/template', handle_pool_tmpl)
        app.router.add_post('/pool/share', handle_pool_share)
        app.router.add_get('/pool/stats', handle_pool_stats)
        app.router.add_get('/ws', handle_ws)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", API_PORT)
        await site.start()
        log.info(f"API: http://0.0.0.0:{API_PORT}")
        await self.p2p.start_server("0.0.0.0", P2P_PORT)
        log.info(f"RAMCOIN v{VERSION} | Белый IP: {MY_WHITE_IP} | H:{self.bc.height}")

        try:
            while self.running:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            log.info("Остановка...")
        finally:
            await self.stop()

    async def stop(self):
        self.running = False
        await self.p2p.stop()
        log.info("Нода остановлена")


async def main():
    node = Node()
    await node.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bye")
    except Exception as e:
        log.critical(f"Fatal: {e}", exc_info=True)