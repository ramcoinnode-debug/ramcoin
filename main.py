#!/usr/bin/env python3
"""
RAMCOIN NODE v7.0.2 — STABLE + POOL + BURN + ADDRESS API
Основа: v7.0.1 (200+ часов). Соло без изменений.
Пул: 98% майнерам, 1% сжигание, 1% разработчику.
"""

import asyncio, hashlib, json, os, time, array, sqlite3, logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from aiohttp import web
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger('RAMCOIN')

VERSION = "7.0.2"
DEV_ADDR = "RAM_04a9b30816a61686f377f152435f528e542b61eb7f0c9403778fdd19862600eb18a4faffe64d6a88a8077da4bf5bf908b74f2729c7fe044ddf5528521f5dcbd75a"
BURN_ADDR = "RAM_BURN_" + "0"*124
COIN = 100_000_000
DB = "blockchain_v7.db"
INITIAL_REWARD = 10 * COIN
BLOCK_TIME = 30.0
HALVING = 876000
MAX_TARGET = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
SCRATCHPAD_ITER = 4096
BASE_BUFFER_SIZE = 524288
MAX_BUFFER_SIZE = 4194304
MAX_HOME_BUFFER = 1048576
MAX_HOME_CORES = 16
MAX_HOME_L3_MB = 64
MAX_HOME_THREADS = 8
SERVER_PENALTY = 0.25
FIXED_FEE = 0.001 * COIN
DEV_SHARE = 10
POOL_FEE = 0.01
BURN_FEE = 0.01
POOL_DIFF_FACTOR = 100
RATE_LIMIT = 10
RATE_WINDOW = 1.0
CPU_WORKERS = min(32, (os.cpu_count() or 4) * 2)
executor = ThreadPoolExecutor(max_workers=CPU_WORKERS)


class Blockchain:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.mempool = []
        self.chain = []
        self.height = 0
        self.accounts = {DEV_ADDR: 100 * COIN}
        self.nonces = {DEV_ADDR: 0}
        self.target = MAX_TARGET // 5
        self.total_tx = 0
        self.start_time = time.time()
        self.accepted = 0
        self.rejected = 0
        self.reject_reasons = {}
        self.ws_clients = set()
        self.request_times = {}
        self._cache = {}
        self._cache_ts = {}
        self.miner_stats = {}
        self.pool_shares = {}
        self.pool_total_shares = 0
        self.pool_template = None
        self.pool_template_ts = 0
        self.init_db()
        if not self.load():
            self.create_genesis()
        log.info(f"NODE v{VERSION} | Height: {self.height} | Diff: {self.fmt_diff()}")

    def init_db(self):
        with sqlite3.connect(DB) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS blocks (idx INTEGER PRIMARY KEY, data TEXT, hash TEXT UNIQUE)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, val TEXT)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS transactions (tx_hash TEXT PRIMARY KEY, block_idx INTEGER, sender TEXT, recipient TEXT, amount INTEGER, fee INTEGER, timestamp INTEGER)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS pool_shares (id INTEGER PRIMARY KEY AUTOINCREMENT, miner_address TEXT, shares INTEGER, timestamp INTEGER)''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_tx_sender ON transactions(sender)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_tx_recipient ON transactions(recipient)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_idx)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_pool_miner ON pool_shares(miner_address)')
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=-65536')

    def load(self):
        try:
            with sqlite3.connect(DB) as conn:
                for key in ['height', 'accounts', 'nonces', 'target', 'total_tx', 'accepted', 'rejected']:
                    row = conn.execute("SELECT val FROM state WHERE key=?", (key,)).fetchone()
                    if not row: return False
                    val = row[0]
                    if key == 'height': self.height = int(val)
                    elif key in ('accounts', 'nonces'): setattr(self, key, json.loads(val))
                    elif key == 'target': self.target = int(val)
                    elif key == 'total_tx': self.total_tx = int(val)
                    elif key == 'accepted': self.accepted = int(val)
                    elif key == 'rejected': self.rejected = int(val)
                rows = conn.execute("SELECT data FROM blocks ORDER BY idx").fetchall()
                self.chain = [json.loads(r[0]) for r in rows]
                self.height = len(self.chain)
            return True
        except: return False

    def save_block(self, block):
        with sqlite3.connect(DB) as conn:
            conn.execute("INSERT OR REPLACE INTO blocks VALUES (?,?,?)", (block['index'], json.dumps(block), block['hash']))
            conn.execute("INSERT OR REPLACE INTO state VALUES ('height',?)", (str(block['index']),))
            for tx in block.get("transactions", []):
                conn.execute("INSERT OR IGNORE INTO transactions VALUES (?,?,?,?,?,?,?)",
                             (tx.get("signature", ""), block['index'], tx.get("sender", ""), tx.get("recipient", ""),
                              int(tx.get("amount", 0)), int(tx.get("fee", FIXED_FEE)), block.get("timestamp", 0)))

    def save_state(self):
        with sqlite3.connect(DB) as conn:
            for key, val in [('accounts', self.accounts), ('nonces', self.nonces), ('target', self.target),
                             ('total_tx', self.total_tx), ('accepted', self.accepted), ('rejected', self.rejected)]:
                conn.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, json.dumps(val) if isinstance(val, dict) else str(val)))

    def calc_hash(self, block):
        c = block.copy(); c.pop("hash", None); c.pop("miner_signature", None)
        return hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()

    def fmt_diff(self):
        if self.target == 0: return "∞"
        sd = MAX_TARGET / self.target
        if sd >= 1e9: return f"{sd/1e9:.2f} GRam/s"
        if sd >= 1e6: return f"{sd/1e6:.2f} MRam/s"
        if sd >= 1e3: return f"{sd/1e3:.2f} KRam/s"
        return f"{sd:.2f} Ram/s"

    def adjust_target(self):
        if self.height < 2: return
        prev = self.chain[-1]; prev_prev = self.chain[-2]
        actual_time = max(1, prev["timestamp"] - prev_prev["timestamp"])
        factor = max(0.25, min(4.0, BLOCK_TIME / actual_time))
        self.target = min(MAX_TARGET, max(1, int(self.target / factor)))

    def create_scratchpad(self, prev_hash, tid, nseed, buffer_size):
        sp = array.array('Q', [0]) * buffer_size
        seed = int(hashlib.sha256(f"{prev_hash}|{tid}|{nseed}|RAMCOIN_v7|{buffer_size}".encode()).hexdigest(), 16)
        s0, s1 = seed, seed ^ 0xDEADBEEF
        for i in range(buffer_size):
            s1, s0 = s0 & 0xFFFFFFFFFFFFFFFF, s1
            s1 ^= (s1 << 23) & 0xFFFFFFFFFFFFFFFF; s1 ^= (s1 >> 17); s1 ^= s0; s1 ^= (s0 >> 26)
            sp[i] = (s0 + s1) & 0xFFFFFFFFFFFFFFFF
        return sp, seed

    def memhard(self, sp, seed, nonce, nseed, buffer_size):
        mix = seed; mods = 0
        for k in range(SCRATCHPAD_ITER):
            mix = (mix * 0x9E3779B97F4A7C15 + nonce + nseed) & 0xFFFFFFFFFFFFFFFF
            mix ^= (mix >> 33); mix ^= (mix << 13)
            idx = mix % buffer_size; rv = sp[idx]
            sp[idx] = (rv ^ mix ^ nonce) & 0xFFFFFFFFFFFFFFFF; mods += 1
            mix = (mix + rv) & 0xFFFFFFFFFFFFFFFF
            if k % 256 == 0:
                idx2 = ((idx * 1103515245 + 12345) ^ rv) % buffer_size
                sp[idx2] = (sp[idx2] ^ (mix >> 16) ^ nonce) & 0xFFFFFFFFFFFFFFFF; mods += 1
            if k > 0 and k % 50000 == 0: nseed = (nseed + 1) & 0xFFFFFFFF; mix = (mix ^ nseed) & 0xFFFFFFFFFFFFFFFF
        return mix, nseed, mods

    def verify_pow_sync(self, block, target_override=None):
        try:
            buffer_size = int(block.get("scratchpad_size", BASE_BUFFER_SIZE))
            if buffer_size < BASE_BUFFER_SIZE or buffer_size > MAX_BUFFER_SIZE: return False
            sp, seed = self.create_scratchpad(str(block["previous_hash"]), int(block.get("extra_nonce", 0)), int(block.get("nonce_seed", 0)), buffer_size)
            mix, _, mods = self.memhard(sp, seed, int(block["nonce"]), int(block.get("nonce_seed", 0)), buffer_size)
            expected = SCRATCHPAD_ITER + (SCRATCHPAD_ITER // 256) + (SCRATCHPAD_ITER // 50000)
            if mods < expected - 10 or mods > expected + 10: return False
            proof = hashlib.sha256(f"{mix}{block['previous_hash']}{block.get('nonce_seed', 0)}{mods}".encode()).hexdigest()
            target = target_override if target_override else self.target
            return proof == block.get("memory_proof", "") and int(proof, 16) <= target
        except: return False

    async def verify_pow_async(self, block, target_override=None):
        return await asyncio.get_event_loop().run_in_executor(executor, self.verify_pow_sync, block, target_override)

    def verify_miner_sig(self, block):
        try:
            addr = block.get("miner_payout_address", ""); sig = block.get("miner_signature", "")
            if not addr.startswith("RAM_") or len(sig) < 128: return False
            pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), bytes.fromhex(addr[4:]))
            data = {"index": block["index"], "previous_hash": block["previous_hash"], "timestamp": block["timestamp"],
                    "nonce": block["nonce"], "nonce_seed": block.get("nonce_seed", 0), "memory_proof": block["memory_proof"],
                    "miner_payout_address": addr, "scratchpad_mods": block.get("scratchpad_mods", 0)}
            pub.verify(bytes.fromhex(sig), json.dumps(data, sort_keys=True).encode(), ec.ECDSA(hashes.SHA256()))
            return True
        except: return False

    def detect_server_miner(self, block):
        if int(block.get("scratchpad_size", BASE_BUFFER_SIZE)) > MAX_HOME_BUFFER: return True
        if int(block.get("extra_nonce", 0)) >= MAX_HOME_THREADS: return True
        return False

    def is_server_address(self, address):
        return self.miner_stats.get(address, {}).get("is_server", False)

    def verify_tx(self, tx):
        try:
            sender, recipient, amount = tx.get("sender", ""), tx.get("recipient", ""), int(tx.get("amount", 0))
            if not sender.startswith("RAM_") or not recipient.startswith("RAM_"): return False, "invalid_address"
            if amount <= 0: return False, "invalid_amount"
            if sender == recipient: return False, "self_transfer"
            if int(tx.get("nonce", -1)) != self.nonces.get(sender, 0): return False, "invalid_nonce"
            if self.accounts.get(sender, 0) < amount + FIXED_FEE: return False, "insufficient_balance"
            pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), bytes.fromhex(sender[4:]))
            tx_data = {"sender": sender, "recipient": recipient, "amount": amount, "fee": FIXED_FEE,
                       "nonce": int(tx.get("nonce", 0)), "timestamp": tx.get("timestamp", 0)}
            pub.verify(bytes.fromhex(tx.get("signature", "")), json.dumps(tx_data, sort_keys=True).encode(), ec.ECDSA(hashes.SHA256()))
            return True, "ok"
        except: return False, "tx_error"

    def submit_share(self, miner_address, nonce, nseed, mix, mods, extra_nonce):
        pool_target = min(MAX_TARGET, int(self.target * POOL_DIFF_FACTOR))
        proof = hashlib.sha256(f"{mix}{self.chain[-1]['hash']}{nseed}{mods}".encode()).hexdigest()
        if int(proof, 16) <= pool_target:
            self.pool_shares[miner_address] = self.pool_shares.get(miner_address, 0) + 1
            self.pool_total_shares += 1
            return True
        return False

    def get_pool_template(self):
        now = time.time()
        if self.pool_template and (now - self.pool_template_ts) < 1.0: return self.pool_template
        if not self.chain: return None
        self.pool_template = {"height": self.height, "previous_hash": self.chain[-1]["hash"],
                              "target": self.target, "pool_target": min(MAX_TARGET, int(self.target * POOL_DIFF_FACTOR)),
                              "transactions": self.mempool, "timestamp": int(now)}
        self.pool_template_ts = now
        return self.pool_template

    def distribute_pool_reward(self):
        if self.pool_total_shares == 0: return False
        reward = INITIAL_REWARD // (2 ** (self.height // HALVING))
        dev_fee = int(reward * POOL_FEE)
        burn_amount = int(reward * BURN_FEE)
        miners_share = reward - dev_fee - burn_amount
        self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + dev_fee
        self.accounts[BURN_ADDR] = self.accounts.get(BURN_ADDR, 0) + burn_amount
        for addr, shares in self.pool_shares.items():
            if shares > 0:
                payout = int(miners_share * (shares / self.pool_total_shares))
                if payout > 0: self.accounts[addr] = self.accounts.get(addr, 0) + payout
        self.pool_shares = {}; self.pool_total_shares = 0
        log.info(f"POOL: +{miners_share/COIN:.2f} miners | +{dev_fee/COIN:.2f} dev | BURN {burn_amount/COIN:.2f}")
        return True

    async def add_block(self, block, ip="unknown"):
        async with self.lock:
            idx = int(block["index"])
            if idx != self.height: self.rejected += 1; return False, f"wrong_index"
            prev = self.chain[-1] if self.chain else None
            if not prev or prev["hash"] != block["previous_hash"]: self.rejected += 1; return False, "invalid_previous_hash"
            miner = block.get("miner_payout_address", DEV_ADDR)
            if not miner.startswith("RAM_") or len(miner) != 134: self.rejected += 1; return False, "invalid_miner_address"
            if not self.verify_miner_sig(block): self.rejected += 1; return False, "invalid_signature"
            block_hash = self.calc_hash(block)
            for b in self.chain[-10:]:
                if b.get("hash") == block_hash: self.rejected += 1; return False, "duplicate_block"
            for tx in block.get("transactions", []):
                valid, reason = self.verify_tx(tx)
                if not valid: self.rejected += 1; return False, f"invalid_tx"
            if not await self.verify_pow_async(block): self.rejected += 1; return False, "invalid_pow"

            is_server = self.detect_server_miner(block)
            if is_server: self.miner_stats[miner] = {"is_server": True, "last_seen": time.time()}

            self.distribute_pool_reward()

            reward = INITIAL_REWARD // (2 ** (idx // HALVING))
            if self.is_server_address(miner): reward = int(reward * SERVER_PENALTY)
            self.accounts[miner] = self.accounts.get(miner, 0) + reward

            for tx in block.get("transactions", []):
                s, r, a = tx["sender"], tx["recipient"], int(tx["amount"])
                df = (FIXED_FEE * DEV_SHARE) // 100; mf = FIXED_FEE - df
                self.accounts[s] = self.accounts.get(s, 0) - (a + FIXED_FEE)
                self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + df
                self.accounts[miner] += mf
                self.accounts[r] = self.accounts.get(r, 0) + a
                self.nonces[s] = self.nonces.get(s, 0) + 1; self.total_tx += 1

            self.mempool = [tx for tx in self.mempool if tx["signature"] not in {t["signature"] for t in block.get("transactions", [])}]
            self.adjust_target(); block["target"] = self.target; block["hash"] = block_hash
            self.save_block(block); self.chain.append(block); self.height = idx + 1; self.accepted += 1
            self._cache = {}; self._cache_ts = {}
            asyncio.create_task(self.notify_miners(block))
            if self.accepted % 10 == 0: self.save_state()
            log.info(f"Block #{idx} | +{reward/COIN:.2f} RAM | {miner[:16]}... | {'SERVER' if is_server else 'HOME'} | Diff: {self.fmt_diff()}")
            return True, "ok"

    async def notify_miners(self, block):
        if not self.ws_clients: return
        msg = json.dumps({"event": "new_block", "height": self.height, "hash": block["hash"], "target": self.target, "timestamp": time.time()})
        dead = set()
        for ws in self.ws_clients.copy():
            try: await ws.send_str(msg)
            except: dead.add(ws)
        self.ws_clients -= dead

    def get_chain_data(self, limit=50):
        now = time.time(); ck = f"chain_{limit}"
        if ck in self._cache and (now - self._cache_ts.get(ck, 0)) < 0.5: return self._cache[ck]
        data = {"length": self.height, "chain": self.chain[-limit:] if len(self.chain) > limit else self.chain,
                "current_target": self.target, "diff_string": self.fmt_diff(), "mempool_size": len(self.mempool),
                "fixed_fee": FIXED_FEE, "pool": {"shares": self.pool_total_shares, "miners": len(self.pool_shares)}}
        self._cache[ck] = data; self._cache_ts[ck] = now
        return data

    def get_stats(self):
        now = time.time()
        if "stats" in self._cache and (now - self._cache_ts.get("stats", 0)) < 0.5: return self._cache["stats"]
        total_ram = sum(self.accounts.values()) / COIN
        data = {"version": VERSION, "height": self.height, "target": self.target, "difficulty": self.fmt_diff(),
                "total_supply": total_ram, "accounts": len(self.accounts), "active_miners": len(self.ws_clients),
                "mempool_size": len(self.mempool), "total_transactions": self.total_tx,
                "accepted_blocks": self.accepted, "rejected_blocks": self.rejected,
                "uptime": int(time.time() - self.start_time),
                "reward": INITIAL_REWARD / COIN / (2 ** (self.height // HALVING)) if self.height > 0 else 10.0,
                "fee": FIXED_FEE / COIN, "pool": {"shares": self.pool_total_shares, "miners": len(self.pool_shares)},
                "burn_total": self.accounts.get(BURN_ADDR, 0) / COIN}
        self._cache["stats"] = data; self._cache_ts["stats"] = now
        return data

    def get_block(self, idx):
        try:
            idx = int(idx)
            if 0 <= idx < self.height: return self.chain[idx]
        except: pass
        return None

    def get_address(self, addr):
        if not addr.startswith("RAM_"): return None
        balance = self.accounts.get(addr, 0) / COIN
        nonce = self.nonces.get(addr, 0)
        txs = []
        try:
            with sqlite3.connect(DB) as conn:
                rows = conn.execute("SELECT * FROM transactions WHERE sender=? OR recipient=? ORDER BY block_idx DESC LIMIT 20", (addr, addr)).fetchall()
                for r in rows: txs.append({"tx_hash": r[0], "block_index": r[1], "sender": r[2], "recipient": r[3], "amount": r[4], "fee": r[5], "timestamp": r[6]})
        except: pass
        return {"address": addr, "balance": balance, "nonce": nonce, "transactions": txs}

    def get_health(self):
        return {"status": "ok", "version": VERSION, "height": self.height, "uptime": int(time.time() - self.start_time),
                "peers": len(self.ws_clients), "mempool": len(self.mempool),
                "last_block_time": self.chain[-1]["timestamp"] if self.chain else 0}

    def check_rate(self, ip):
        now = time.time()
        times = [t for t in self.request_times.get(ip, []) if now - t < RATE_WINDOW]
        if len(times) >= RATE_LIMIT: return False
        times.append(now); self.request_times[ip] = times
        return True

    def create_genesis(self):
        g = {"index": 0, "previous_hash": "0"*64, "transactions": [], "timestamp": int(time.time() - BLOCK_TIME),
             "nonce": 0, "nonce_seed": 0, "memory_proof": "0"*64, "target": self.target,
             "miner_payout_address": DEV_ADDR, "miner_signature": "0"*128, "extra_nonce": 0,
             "scratchpad_mods": 0, "scratchpad_size": BASE_BUFFER_SIZE}
        g["hash"] = self.calc_hash(g)
        self.save_block(g); self.chain.append(g); self.height = 1; self.save_state()
        log.info("Genesis created")


bc = Blockchain()

@web.middleware
async def cors_middleware(request, handler):
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

async def handle_chain(request):
    return web.json_response(bc.get_chain_data(int(request.query.get("limit", 50))))
async def handle_stats(request): return web.json_response(bc.get_stats())
async def handle_health(request): return web.json_response(bc.get_health())
async def handle_block(request):
    b = bc.get_block(request.match_info.get('idx', ''))
    return web.json_response(b) if b else web.json_response({"error": "not found"}, status=404)
async def handle_address(request):
    addr = request.match_info.get('addr', '')
    data = bc.get_address(addr)
    return web.json_response(data) if data else web.json_response({"error": "invalid address"}, status=400)
async def handle_pending(request): return web.json_response(bc.mempool)
async def handle_top(request):
    limit = int(request.query.get("limit", 10))
    sorted_acc = sorted(bc.accounts.items(), key=lambda x: x[1], reverse=True)
    return web.json_response([{"address": a, "balance": b/COIN} for a, b in sorted_acc[:limit]])

async def handle_mine(request):
    if not bc.check_rate(request.remote): return web.json_response({"status": "rejected", "reason": "rate_limit"}, status=429)
    try: block = await request.json()
    except: return web.json_response({"status": "rejected", "reason": "invalid_json"}, status=400)
    success, reason = await bc.add_block(block, request.remote)
    return web.json_response({"status": "ok" if success else "rejected", "reason": reason}, status=200 if success else 400)

async def handle_submit_tx(request):
    try: tx = await request.json()
    except: return web.json_response({"status": "error", "reason": "invalid_json"}, status=400)
    valid, reason = bc.verify_tx(tx)
    if not valid: return web.json_response({"status": "rejected", "reason": reason}, status=400)
    bc.mempool.append(tx)
    return web.json_response({"status": "ok"})

async def handle_pool_template(request):
    tmpl = bc.get_pool_template()
    return web.json_response(tmpl) if tmpl else web.json_response({"error": "no chain"}, status=503)

async def handle_pool_share(request):
    try:
        data = await request.json()
        if not data.get("miner_address", "").startswith("RAM_"): return web.json_response({"status": "rejected"}, status=400)
        valid = bc.submit_share(data["miner_address"], int(data.get("nonce", 0)), int(data.get("nonce_seed", 0)),
                                data.get("mix", "0"), int(data.get("mods", 0)), int(data.get("extra_nonce", 0)))
        return web.json_response({"status": "ok" if valid else "rejected"})
    except: return web.json_response({"status": "error"}, status=400)

async def handle_pool_stats(request):
    return web.json_response({"shares": bc.pool_total_shares, "miners": len(bc.pool_shares)})

async def handle_ws(request):
    ws = web.WebSocketResponse(); await ws.prepare(request)
    bc.ws_clients.add(ws)
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    if data.get("type") == "miner":
                        hw = data.get("hardware", {})
                        bc.miner_stats[hw.get("address", "unknown")] = {"cpu": hw.get("cpu", ""), "cores": hw.get("cores", 0), "l3_mb": hw.get("l3_mb", 0), "is_server": hw.get("is_server", False)}
                except: pass
    finally: bc.ws_clients.discard(ws)
    return ws

async def heartbeat():
    while True:
        await asyncio.sleep(15)
        log.info(f"Height: {bc.height} | Diff: {bc.fmt_diff()} | Miners: {len(bc.ws_clients)} | Pool: {len(bc.pool_shares)}")

async def main():
    app = web.Application(client_max_size=10*1024*1024, middlewares=[cors_middleware])
    app.router.add_get('/chain', handle_chain)
    app.router.add_get('/stats', handle_stats)
    app.router.add_get('/health', handle_health)
    app.router.add_get('/block/{idx}', handle_block)
    app.router.add_get('/address/{addr}', handle_address)
    app.router.add_get('/pending', handle_pending)
    app.router.add_get('/top', handle_top)
    app.router.add_post('/mine', handle_mine)
    app.router.add_post('/tx', handle_submit_tx)
    app.router.add_get('/pool/template', handle_pool_template)
    app.router.add_post('/pool/share', handle_pool_share)
    app.router.add_get('/pool/stats', handle_pool_stats)
    app.router.add_get('/ws', handle_ws)
    if os.path.exists('index.html'): app.router.add_get('/', lambda r: web.FileResponse('index.html'))
    asyncio.create_task(heartbeat())
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 5000)
    log.info(f"NODE v{VERSION} | http://0.0.0.0:5000")
    await site.start()
    await asyncio.Future()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: log.info("Server stopped")