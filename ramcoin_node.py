#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║   RAMCOIN NODE v1.0.0 — GENESIS EDITION              ║
║   Защита: ChaCha20-Poly1305 + ECDH + ECDSA           ║
║   Сеть: P2P + SSL/TLS + Seed-ноды + Peer Exchange    ║
║   Майнинг: Anti-Cheat + Pool + Solo                  ║
║   API: API-Key + RateLimit + DDoS Protection         ║
║   Windows/Linux/MacOS — Python 3.10+                 ║
╚══════════════════════════════════════════════════════╝
"""
import asyncio
import hashlib
import json
import os
import sys
import time
import array
import sqlite3
import logging
import struct
import secrets
import hmac
import ipaddress
import signal
import gc
import traceback
import threading
import io
from typing import Optional, Dict, List, Tuple, Set, Any, Union
from collections import defaultdict, deque, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import IntEnum, Enum
from functools import wraps
import aiohttp
from aiohttp import web, WSMsgType
import lz4.frame
from cryptography.hazmat.primitives.asymmetric import ec, x25519
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# ==================== WINDOWS FIX ====================
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ==================== КОНСТАНТЫ ====================
VERSION = "1.0.0"
PROTOCOL = 2
COIN = 100_000_000
MY_WHITE_IP = os.environ.get("RAMCOIN_IP", "90.188.115.169")

API_KEY_FILE = "api_key.txt"
if os.path.exists(API_KEY_FILE):
    with open(API_KEY_FILE, "r") as f:
        API_KEY = f.read().strip()
else:
    API_KEY = secrets.token_hex(32)
    with open(API_KEY_FILE, "w") as f:
        f.write(API_KEY)

DEV_ADDR = "RAM_04a9b30816a61686f377f152435f528e542b61eb7f0c9403778fdd19862600eb18a4faffe64d6a88a8077da4bf5bf908b74f2729c7fe044ddf5528521f5dcbd75a"
BURN_ADDR = "RAM_BURN_" + "0" * 124

DB_PATH = "blockchain_v10.db"
PEERS_DB = "peers_v10.db"
SEEDS_DB = "seeds_v12.db"

P2P_PORT = int(os.environ.get("P2P_PORT", 8333))
API_PORT = int(os.environ.get("API_PORT", 5000))
METRICS_PORT = int(os.environ.get("METRICS_PORT", 9090))

INITIAL_REWARD = 10 * COIN
MINIMUM_REWARD = int(0.6 * COIN)
BLOCK_TIME = 30.0
HALVING = 876_000
MAX_TARGET = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
INITIAL_TARGET = MAX_TARGET >> 4
MAX_TIME_DRIFT = 7200
MIN_BLOCK_GAP = 5

SCRATCHPAD_ITER = 8192
BASE_SCRATCHPAD = 524288
MAX_SCRATCHPAD = 4194304
MAX_THREADS_PER_MINER = 4
MAX_SCRATCHPAD_SIZE = 8388608
EXPECTED_MODS = SCRATCHPAD_ITER + (SCRATCHPAD_ITER // 256) + (SCRATCHPAD_ITER // 50000)

FIXED_FEE = int(0.001 * COIN)
DEV_FUND_SHARE = 5
POOL_FEE = 0.01
BURN_FEE = 0.01
POOL_DIFF_FACTOR = 100

MAX_PEERS = 500
PEER_TIMEOUT = 300
MAX_MEMPOOL = 10000
MAX_BLOCK_TX = 200
MAX_MEMPOOL_PER_ADDRESS = 50

ANNOUNCE_INTERVAL = 600
MAX_SEED_NODES = 50
SEED_RETENTION = 86400
GOSSIP_CACHE_TTL = 3600
MAX_RELAY_COUNT = 10
PEER_EXCHANGE_COUNT = 20
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 30
API_RATE_LIMIT = 100
MAX_REQUEST_SIZE = 10 * 1024 * 1024
BAN_TIME = 3600
MAX_BAN_SCORE = 10

BOOTSTRAP_SEEDS = [
    "seed1.ramcoin.network:8333",
    "seed2.ramcoin.network:8333",
    "seed3.ramcoin.network:8333",
]

CPU_WORKERS = min(8, (os.cpu_count() or 2))
executor = ThreadPoolExecutor(max_workers=CPU_WORKERS)

# ==================== PROMETHEUS МЕТРИКИ ====================
PEERS_GAUGE = Gauge('ramcoin_peers_total', 'Total peers')
CONNECTIONS_GAUGE = Gauge('ramcoin_connections_active', 'Active connections')
SEEDS_GAUGE = Gauge('ramcoin_seeds_total', 'Total seed nodes')
HEIGHT_GAUGE = Gauge('ramcoin_height', 'Current blockchain height')
MEMPOOL_SIZE = Gauge('ramcoin_mempool_size', 'Mempool size')
BLOCK_TIME_HISTOGRAM = Histogram('ramcoin_block_time_seconds', 'Block time', buckets=[5, 10, 20, 30, 60, 120, 300])
TX_COUNTER = Counter('ramcoin_transactions_total', 'Total transactions processed')
BLOCKS_COUNTER = Counter('ramcoin_blocks_total', 'Total blocks', ['status'])
REPUTATION_GAUGE = Gauge('ramcoin_average_reputation', 'Average seed reputation')
API_REQUESTS = Counter('ramcoin_api_requests_total', 'API requests', ['endpoint', 'status'])
ERRORS_COUNTER = Counter('ramcoin_errors_total', 'Total errors', ['type'])

# ==================== ЛОГГИРОВАНИЕ ====================
class SecureFormatter(logging.Formatter):
    def format(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = record.msg.replace(API_KEY, "***API_KEY***")
        return super().format(record)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(SecureFormatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S'))

file_handler = logging.FileHandler('ramcoin.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(SecureFormatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S'))

logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
log = logging.getLogger('RAMCOIN')


# ==================== ENUMS ====================
class OffenseType(IntEnum):
    SPAM = 1
    INVALID_BLOCK = 2
    DOUBLE_SPEND = 3
    SYBIL_ATTEMPT = 4
    ECLIPSE_ATTEMPT = 5
    PROTOCOL_VIOLATION = 6
    INVALID_PROOF = 7
    DDoS_ATTEMPT = 8
    API_ABUSE = 9


class NetworkHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class NodeType(Enum):
    SEED = "seed"
    PUBLIC = "public"
    PRIVATE = "private"


# ==================== DATA CLASSES ====================
@dataclass
class PeerInfo:
    addr: str
    ip: str
    port: int
    last_seen: float = 0
    height: int = 0
    node_type: str = "private"
    version: str = ""
    ban_score: int = 0


# ==================== КРИПТОГРАФИЯ ====================
class CryptoUtils:
    @staticmethod
    def generate_ephemeral_keypair():
        private_key = x25519.X25519PrivateKey.generate()
        return private_key, private_key.public_key()

    @staticmethod
    def derive_shared_key(private_key, peer_public_bytes: bytes) -> bytes:
        peer_public = x25519.X25519PublicKey.from_public_bytes(peer_public_bytes)
        shared_key = private_key.exchange(peer_public)
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"RAMCOIN_P2P_ENCRYPTION_V2").derive(shared_key)

    @staticmethod
    def encrypt_message(key: bytes, plaintext: bytes) -> bytes:
        if len(plaintext) > 1024:
            plaintext = lz4.frame.compress(plaintext)
            compressed = True
        else:
            compressed = False
        nonce = secrets.token_bytes(12)
        cipher = ChaCha20Poly1305(key)
        data = struct.pack('?', compressed) + plaintext
        return nonce + cipher.encrypt(nonce, data, b"RAMCOIN_P2P_V2")

    @staticmethod
    def decrypt_message(key: bytes, encrypted_data: bytes) -> bytes:
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        cipher = ChaCha20Poly1305(key)
        decrypted = cipher.decrypt(nonce, ciphertext, b"RAMCOIN_P2P_V2")
        compressed = struct.unpack('?', decrypted[:1])[0]
        data = decrypted[1:]
        return lz4.frame.decompress(data) if compressed else data


class IPUtils:
    @staticmethod
    def is_public_ip(ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
            return not (addr.is_private or addr.is_loopback or addr.is_multicast or addr.is_reserved or addr.is_unspecified)
        except:
            return False

    @staticmethod
    def get_ip_range(ip: str, prefix: int = None) -> str:
        try:
            addr = ipaddress.ip_address(ip)
            prefix = prefix or (24 if isinstance(addr, ipaddress.IPv4Address) else 64)
            if isinstance(addr, ipaddress.IPv4Address):
                return str(ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False).network_address)
            return str(ipaddress.IPv6Network(f"{ip}/{prefix}", strict=False).network_address)
        except:
            return ip

    @staticmethod
    def is_same_subnet(ip1: str, ip2: str, prefix: int = 24) -> bool:
        try:
            return IPUtils.get_ip_range(ip1, prefix) == IPUtils.get_ip_range(ip2, prefix)
        except:
            return False

    @staticmethod
    def detect_node_type(ip: str) -> str:
        if not ip or ip in ("0.0.0.0", "127.0.0.1", "::1", "localhost"):
            return NodeType.PRIVATE.value
        if IPUtils.is_public_ip(ip):
            return NodeType.PUBLIC.value
        return NodeType.PRIVATE.value


class SecureRateLimiter:
    def __init__(self):
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.banned: Dict[str, float] = {}
        self.scores: Dict[str, int] = defaultdict(int)
        self.lock = threading.Lock()

    def check(self, key: str, limit: int = RATE_LIMIT_MAX_REQUESTS, window: int = RATE_LIMIT_WINDOW) -> bool:
        now = time.time()
        with self.lock:
            if key in self.banned and now < self.banned[key]:
                return False
            if key in self.banned:
                del self.banned[key]
            self.requests[key] = [t for t in self.requests[key] if now - t < window]
            effective_limit = max(1, limit - self.scores.get(key, 0))
            if len(self.requests[key]) >= effective_limit:
                self.scores[key] += 1
                if self.scores[key] >= MAX_BAN_SCORE:
                    self.banned[key] = now + BAN_TIME * (2 ** (self.scores[key] - MAX_BAN_SCORE))
                    log.warning(f"🚫 BAN: {key}")
                return False
            self.requests[key].append(now)
            return True

    def cleanup(self):
        now = time.time()
        with self.lock:
            expired = [k for k, v in self.requests.items() if not [t for t in v if now - t < RATE_LIMIT_WINDOW]]
            for k in expired:
                del self.requests[k]
            expired_bans = [k for k, v in self.banned.items() if now >= v]
            for k in expired_bans:
                del self.banned[k]
                self.scores[k] = max(0, self.scores.get(k, 0) - 1)


# ==================== SEED REGISTRY ====================
class SeedRegistry:
    def __init__(self):
        self.seeds: Dict[str, PeerInfo] = {}
        self.reputation: Dict[str, float] = defaultdict(float)
        self.lock = asyncio.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(SEEDS_DB) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS seeds
                (addr TEXT PRIMARY KEY, ip TEXT, port INTEGER, reputation REAL,
                 last_seen REAL, height INTEGER, version TEXT, node_type TEXT)''')
            conn.execute('PRAGMA journal_mode=WAL')

    async def add_seed(self, ip: str, port: int, height: int, version: str = "", node_type: str = "public") -> bool:
        async with self.lock:
            if not IPUtils.is_public_ip(ip):
                return False
            addr = f"{ip}:{port}"
            now = time.time()
            self.seeds[addr] = PeerInfo(
                addr=addr, ip=ip, port=port, last_seen=now,
                height=height, version=version, node_type=node_type
            )
            self.reputation[addr] = min(100.0, self.reputation.get(addr, 1.0) + 0.1)
            await self._save_seed(addr)
            SEEDS_GAUGE.set(len(self.seeds))
            return True

    def get_active_seeds(self, limit: int = MAX_SEED_NODES) -> List[PeerInfo]:
        now = time.time()
        active = [info for addr, info in self.seeds.items() if now - info.last_seen < SEED_RETENTION]
        active.sort(key=lambda x: self.reputation.get(x.addr, 0), reverse=True)
        return active[:limit]

    def get_peers_for_exchange(self, count: int = PEER_EXCHANGE_COUNT) -> List[dict]:
        active = self.get_active_seeds(count * 2)
        peers = []
        for info in active[:count]:
            peers.append({
                "ip": info.ip, "port": info.port,
                "height": info.height, "node_type": info.node_type
            })
        return peers

    async def update_peer_info(self, ip: str, port: int, height: int, version: str = "", node_type: str = "private"):
        async with self.lock:
            addr = f"{ip}:{port}"
            now = time.time()
            if addr in self.seeds:
                self.seeds[addr].last_seen = now
                self.seeds[addr].height = height
                self.seeds[addr].version = version
                self.seeds[addr].node_type = node_type
            else:
                self.seeds[addr] = PeerInfo(
                    addr=addr, ip=ip, port=port, last_seen=now,
                    height=height, version=version, node_type=node_type
                )
                self.reputation[addr] = 1.0

    async def _save_seed(self, addr: str):
        try:
            if addr not in self.seeds:
                return
            info = self.seeds[addr]
            with sqlite3.connect(SEEDS_DB, timeout=10) as conn:
                conn.execute("INSERT OR REPLACE INTO seeds VALUES (?,?,?,?,?,?,?,?)",
                    (addr, info.ip, info.port, self.reputation.get(addr, 0),
                     info.last_seen, info.height, info.version, info.node_type))
        except:
            pass

    async def cleanup(self):
        async with self.lock:
            now = time.time()
            dead = [addr for addr, info in self.seeds.items() if now - info.last_seen > SEED_RETENTION * 3]
            for addr in dead:
                del self.seeds[addr]
                self.reputation.pop(addr, None)
            if dead:
                log.info(f"🧹 Очищено {len(dead)} seed-нод")

    def get_stats(self) -> dict:
        active = sum(1 for info in self.seeds.values() if time.time() - info.last_seen < SEED_RETENTION)
        avg_rep = sum(self.reputation.values()) / max(1, len(self.reputation))
        return {"total": len(self.seeds), "active": active, "average_reputation": avg_rep}


# ==================== PROOF OF WORK ====================
def create_scratchpad_sync(prev_hash: str, tid: int, nseed: int, buffer_size: int) -> Tuple[array.array, int]:
    sp = array.array('Q', [0]) * buffer_size
    seed_str = f"{prev_hash}|{tid}|{nseed}|RAMCOIN_v7|{buffer_size}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
    s0, s1 = seed, seed ^ 0xDEADBEEF
    for i in range(buffer_size):
        s1, s0 = s0 & 0xFFFFFFFFFFFFFFFF, s1
        s1 ^= (s1 << 23) & 0xFFFFFFFFFFFFFFFF
        s1 ^= (s1 >> 17)
        s1 ^= s0
        s1 ^= (s0 >> 26)
        sp[i] = (s0 + s1) & 0xFFFFFFFFFFFFFFFF
    return sp, seed


def memhard_sync(sp: array.array, seed: int, nonce: int, nseed: int, buffer_size: int) -> Tuple[int, int, int]:
    sp_copy = sp[:]
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


def verify_pow_sync(block: dict, target: int) -> bool:
    try:
        buffer_size = int(block.get("scratchpad_size", BASE_SCRATCHPAD))
        if not (BASE_SCRATCHPAD <= buffer_size <= MAX_SCRATCHPAD):
            return False
        sp, seed = create_scratchpad_sync(
            str(block["previous_hash"]),
            int(block.get("extra_nonce", 0)),
            int(block.get("nonce_seed", 0)),
            buffer_size
        )
        mix, new_nseed, mods = memhard_sync(
            sp, seed,
            int(block["nonce"]),
            int(block.get("nonce_seed", 0)),
            buffer_size
        )
        if mods != EXPECTED_MODS:
            return False
        proof = hashlib.sha256(f"{mix}{block['previous_hash']}{new_nseed}{mods}".encode()).hexdigest()
        return hmac.compare_digest(proof.encode(), block.get("memory_proof", "").encode()) and int(proof, 16) <= target
    except:
        return False


async def verify_pow_async(block: dict, target: int) -> bool:
    return await asyncio.get_event_loop().run_in_executor(executor, verify_pow_sync, block, target)


# ==================== БЛОКЧЕЙН ====================
class Blockchain:
    def __init__(self, p2p=None):
        self.p2p = p2p
        self.lock = asyncio.Lock()
        self.share_lock = asyncio.Lock()
        self.mempool_lock = asyncio.Lock()
        self.chain: List[dict] = []
        self.height = 0
        self.accounts: Dict[str, int] = {DEV_ADDR: 100 * COIN}
        self.nonces: Dict[str, int] = {DEV_ADDR: 0}
        self.target = INITIAL_TARGET
        self.total_tx = 0
        self.accepted = 0
        self.rejected = 0
        self.start_time = time.time()
        self.last_block_time = 0
        self.mempool: deque = deque(maxlen=MAX_MEMPOOL)
        self.mempool_hashes: Set[str] = set()
        self.mempool_by_sender: Dict[str, int] = defaultdict(int)
        self.pool_shares: Dict[str, int] = defaultdict(int)
        self.pool_total = 0
        self.pool_template = None
        self.pool_template_ts = 0
        self.ws_clients: Set[web.WebSocketResponse] = set()
        self.orphans: Dict[str, dict] = {}
        self.startup_ok = True

        self._init_db()
        if not self._load():
            self._create_genesis()

        log.info(f"✅ RAMCOIN v{VERSION} | H:{self.height} | D:{self.fmt_diff()} | Аккаунтов: {len(self.accounts)}")
        HEIGHT_GAUGE.set(self.height)
        asyncio.create_task(self.periodic_cleanup())

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS blocks (idx INTEGER PRIMARY KEY, data TEXT, hash TEXT)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, val TEXT)''')
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')

    def _load(self) -> bool:
        try:
            if not os.path.exists(DB_PATH):
                return False
            with sqlite3.connect(DB_PATH) as conn:
                required = ['target', 'total_tx', 'accepted', 'rejected']
                for key in required:
                    if not conn.execute("SELECT val FROM state WHERE key=?", (key,)).fetchone():
                        return False

                self.target = int(conn.execute("SELECT val FROM state WHERE key='target'").fetchone()[0])
                self.total_tx = int(conn.execute("SELECT val FROM state WHERE key='total_tx'").fetchone()[0])
                self.accepted = int(conn.execute("SELECT val FROM state WHERE key='accepted'").fetchone()[0])
                self.rejected = int(conn.execute("SELECT val FROM state WHERE key='rejected'").fetchone()[0])

                rows = conn.execute("SELECT data FROM blocks ORDER BY idx").fetchall()
                self.chain = [json.loads(r[0]) for r in rows]
                self.height = len(self.chain)

                if self.height == 0:
                    return False

                for i in range(self.height):
                    new_hash = self.calc_hash(self.chain[i])
                    if self.chain[i].get("hash") != new_hash:
                        self.chain[i]["hash"] = new_hash
                        try:
                            conn.execute("UPDATE blocks SET hash=? WHERE idx=?", (new_hash, i))
                        except:
                            pass
                    if i > 0:
                        self.chain[i]["previous_hash"] = self.chain[i - 1]["hash"]

                state_height = conn.execute("SELECT val FROM state WHERE key='height'").fetchone()
                if state_height and int(state_height[0]) != self.height:
                    log.warning(f"⚠️ Высота в state ({state_height[0]}) != цепочке ({self.height}). Исправляю.")

                accounts_row = conn.execute("SELECT val FROM state WHERE key='accounts'").fetchone()
                nonces_row = conn.execute("SELECT val FROM state WHERE key='nonces'").fetchone()
                if accounts_row:
                    self.accounts = json.loads(accounts_row[0])
                if nonces_row:
                    self.nonces = json.loads(nonces_row[0])

                if not self.accounts:
                    self._rebuild_state()

                conn.commit()
                log.info(f"📦 Загружено {self.height} блоков")
                return True
        except Exception as e:
            log.error(f"Ошибка загрузки цепи: {e}")
            return False

    def _rebuild_state(self):
        log.warning("🔄 Пересборка состояния из цепочки...")
        self.accounts = {DEV_ADDR: 100 * COIN}
        self.nonces = {DEV_ADDR: 0}
        for block in self.chain:
            for tx in block.get("transactions", []):
                s, r, a = tx["sender"], tx["recipient"], int(tx["amount"])
                fee = int(tx.get("fee", FIXED_FEE))
                if self.accounts.get(s, 0) >= a + fee:
                    self.accounts[s] = self.accounts.get(s, 0) - (a + fee)
                    self.accounts[r] = self.accounts.get(r, 0) + a
                    df = (fee * 15) // 100
                    self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + df
                    self.nonces[s] = self.nonces.get(s, 0) + 1
            miner = block.get("miner_payout_address", "")
            reward = self.reward_at(block["index"])
            total_fees = block.get("total_fees", 0)
            if block.get("pool_block", False) and self.pool_total > 0:
                pass
            else:
                self.accounts[miner] = self.accounts.get(miner, 0) + reward + total_fees
            dev_fund = self.dev_fund_share(block["index"], reward)
            if dev_fund > 0:
                self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + dev_fund
                if not block.get("pool_block", False):
                    self.accounts[miner] = self.accounts.get(miner, 0) - dev_fund
        log.info(f"✅ Состояние пересобрано. Аккаунтов: {len(self.accounts)}")

    def _create_genesis(self):
        g = {
            "index": 0, "previous_hash": "0" * 64, "transactions": [],
            "timestamp": int(time.time() - BLOCK_TIME),
            "nonce": 0, "nonce_seed": 0, "memory_proof": "0" * 64,
            "target": self.target, "miner_payout_address": DEV_ADDR,
            "miner_signature": "0" * 128, "extra_nonce": 0,
            "scratchpad_mods": 0, "scratchpad_size": BASE_SCRATCHPAD,
            "total_fees": 0, "dev_fund": 0,
            "version": PROTOCOL, "threads_used": 1
        }
        g["hash"] = self.calc_hash(g)
        self._save_block(g)
        self.chain.append(g)
        self.height = 1
        self.last_block_time = g["timestamp"]
        self.accepted = 1

    def _save_block(self, block: dict):
        try:
            with sqlite3.connect(DB_PATH, timeout=30) as conn:
                conn.execute("INSERT OR REPLACE INTO blocks VALUES (?,?,?)",
                    (block['index'], json.dumps(block), block['hash']))
                for key, val in [
                    ('height', str(self.height)),
                    ('accounts', json.dumps(self.accounts)),
                    ('nonces', json.dumps(self.nonces)),
                    ('target', str(self.target)),
                    ('total_tx', str(self.total_tx)),
                    ('accepted', str(self.accepted)),
                    ('rejected', str(self.rejected))
                ]:
                    conn.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, val))
                conn.commit()
        except Exception as e:
            log.error(f"Ошибка сохранения блока: {e}")

    def calc_hash(self, block: dict) -> str:
        c = block.copy()
        c.pop("hash", None)
        return hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()

    def fmt_diff(self) -> str:
        if self.target <= 0:
            return "∞"
        sd = MAX_TARGET / self.target
        if sd >= 1e12: return f"{sd / 1e12:.2f} TRam/s"
        if sd >= 1e9:  return f"{sd / 1e9:.2f} GRam/s"
        if sd >= 1e6:  return f"{sd / 1e6:.2f} MRam/s"
        if sd >= 1e3:  return f"{sd / 1e3:.2f} KRam/s"
        return f"{sd:.2f} Ram/s"

    def _adjust_target(self):
        if self.height < 2:
            return
        actual_time = self.chain[-1]["timestamp"] - self.chain[-2]["timestamp"]
        actual_time = max(MIN_BLOCK_GAP, min(actual_time, BLOCK_TIME * 10))
        if actual_time < 10:    adjustment = 0.65
        elif actual_time < 20:  adjustment = 0.80
        elif actual_time < 25:  adjustment = 0.90
        elif actual_time <= 35: adjustment = 1.0
        elif actual_time < 50:  adjustment = 1.10
        elif actual_time < 90:  adjustment = 1.25
        else:                   adjustment = 1.40
        new_target = int(self.target * adjustment)
        new_target = max(MAX_TARGET // 1000000, min(MAX_TARGET // 2, new_target))
        self.target = new_target

    def reward_at(self, h: int) -> int:
        x = h // HALVING
        base = 0 if x >= 64 else INITIAL_REWARD >> x
        return max(base, MINIMUM_REWARD)

    def dev_fund_share(self, h: int, reward: int) -> int:
        return int(reward * DEV_FUND_SHARE / 100)

    def verify_block_signature(self, block: dict) -> bool:
        if block.get("pool_block", False):
            return True
        miner_address = block.get("miner_payout_address", "")
        if not miner_address.startswith("RAM_"):
            return False
        signature_hex = block.get("miner_signature", "")
        if not signature_hex or len(signature_hex) < 10:
            return False
        try:
            pub_hex = miner_address[4:]
            pub_bytes = bytes.fromhex(pub_hex)
            pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub_bytes)
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
        except:
            return False

    def verify_tx_signature(self, tx: dict) -> bool:
        try:
            sender = tx.get("sender", "")
            if not sender.startswith("RAM_"):
                return False
            pub_hex = sender[4:]
            pub_bytes = bytes.fromhex(pub_hex)
            pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub_bytes)
            signing_data = OrderedDict([
                ("amount", int(tx["amount"])),
                ("fee", int(tx.get("fee", FIXED_FEE))),
                ("nonce", int(tx["nonce"])),
                ("recipient", tx["recipient"]),
                ("sender", tx["sender"]),
                ("timestamp", int(tx["timestamp"]))
            ])
            hash_bytes = json.dumps(signing_data).encode()
            signature = bytes.fromhex(tx.get("signature", ""))
            pub_key.verify(signature, hash_bytes, ec.ECDSA(hashes.SHA256()))
            return True
        except:
            return False

    async def add_block(self, block: dict, source: str = "unknown") -> Tuple[bool, str]:
        async with self.lock:
            idx = int(block.get("index", -1))

            if idx > self.height:
                self.orphans[block.get("hash", "")] = block
                log.info(f"👻 Орфанный блок #{idx}")
                return False, "orphan_future"

            if idx < self.height:
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

            if not await verify_pow_async(block, self.target):
                self.rejected += 1
                return False, "pow"

            if not self.verify_block_signature(block):
                self.rejected += 1
                return False, "block_signature"

            threads_used = block.get("threads_used", 1)
            ram_used = block.get("scratchpad_size", BASE_SCRATCHPAD)
            if threads_used > MAX_THREADS_PER_MINER:
                self.rejected += 1
                log.warning(f"🚫 ЧИТЕР: {threads_used} потоков")
                return False, "cheater_threads"
            if ram_used > MAX_SCRATCHPAD_SIZE:
                self.rejected += 1
                log.warning(f"🚫 ЧИТЕР: RAM {ram_used // 1024 // 1024}MB")
                return False, "cheater_ram"

            log.info(f"✅ Честный майнинг: {threads_used} потока × {ram_used // 1024 // 1024}MB")

            miner = block.get("miner_payout_address", "")
            is_pool = block.get("pool_block", False)
            validated_txs = []
            total_fees = 0

            for tx in block.get("transactions", []):
                if not self.verify_tx_signature(tx):
                    self.rejected += 1
                    return False, "tx_signature"

                s, r, a = tx["sender"], tx["recipient"], int(tx["amount"])
                fee = int(tx.get("fee", FIXED_FEE))
                tx_nonce = int(tx["nonce"])
                expected_nonce = self.nonces.get(s, 0)

                if tx_nonce != expected_nonce:
                    self.rejected += 1
                    return False, "invalid_nonce"
                if self.accounts.get(s, 0) < a + fee:
                    continue

                validated_txs.append(tx)
                self.accounts[s] = self.accounts.get(s, 0) - (a + fee)
                self.accounts[r] = self.accounts.get(r, 0) + a
                self.nonces[s] = expected_nonce + 1
                self.total_tx += 1
                total_fees += fee

            reward = self.reward_at(idx)
            dev_fund = self.dev_fund_share(idx, reward)

            if is_pool and self.pool_total > 0:
                df_pool = int(reward * POOL_FEE)
                bn_pool = int(reward * BURN_FEE)
                ms = reward - df_pool - bn_pool
                if dev_fund > 0:
                    ms -= dev_fund
                self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + df_pool + dev_fund
                self.accounts[BURN_ADDR] = self.accounts.get(BURN_ADDR, 0) + bn_pool
                for a, s in list(self.pool_shares.items()):
                    if s > 0:
                        p = int(ms * s / self.pool_total)
                        if p > 0:
                            self.accounts[a] = self.accounts.get(a, 0) + p
                self.pool_shares.clear()
                self.pool_total = 0
            else:
                miner_reward = reward - dev_fund + total_fees
                self.accounts[miner] = self.accounts.get(miner, 0) + miner_reward
                if dev_fund > 0:
                    self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + dev_fund

            async with self.mempool_lock:
                tx_sigs = {tx.get("signature") for tx in validated_txs}
                self.mempool_hashes -= tx_sigs
                new_mempool = deque(maxlen=MAX_MEMPOOL)
                for tx in self.mempool:
                    sig = tx.get("signature", "")
                    if sig not in tx_sigs:
                        new_mempool.append(tx)
                    else:
                        s = tx.get("sender", "")
                        self.mempool_by_sender[s] = max(0, self.mempool_by_sender.get(s, 0) - 1)
                self.mempool = new_mempool

            self._adjust_target()
            block["target"] = self.target
            block["total_fees"] = total_fees
            block["dev_fund"] = dev_fund
            block["hash"] = self.calc_hash(block)
            self._save_block(block)
            self.chain.append(block)
            self.height += 1
            self.last_block_time = block["timestamp"]
            self.accepted += 1
            BLOCKS_COUNTER.labels(status="accepted").inc()

            HEIGHT_GAUGE.set(self.height)
            TX_COUNTER.inc(len(validated_txs))
            MEMPOOL_SIZE.set(len(self.mempool))
            BLOCK_TIME_HISTOGRAM.observe(time.time() - self.last_block_time)

            asyncio.create_task(self._notify(block))
            if self.p2p:
                asyncio.create_task(self.p2p.broadcast_block(block))

            log.info(f"#{idx} | {'POOL' if is_pool else 'SOLO'} | +{reward / COIN:.2f} RAM | "
                     f"Fees:{total_fees / COIN:.4f} | DevFund:{dev_fund / COIN:.4f} | H:{self.height}")
            return True, "ok"

    async def submit_share(self, addr: str, nonce: int, nseed: int, mix: str, mods: int,
                           extra: int, size: int) -> bool:
        async with self.share_lock:
            if not self.chain:
                return False
            prev_hash = self.get_pool_template()["previous_hash"]
            proof = hashlib.sha256(f"{mix}{prev_hash}{nseed}{mods}".encode()).hexdigest()
            proof_int = int(proof, 16)
            pool_target = min(MAX_TARGET, int(self.target * POOL_DIFF_FACTOR))
            if proof_int <= self.target:
                block = {
                    "index": self.height, "previous_hash": prev_hash,
                    "timestamp": int(time.time()), "nonce": nonce,
                    "nonce_seed": nseed, "memory_proof": proof,
                    "target": self.target, "extra_nonce": extra,
                    "miner_payout_address": addr, "scratchpad_mods": mods,
                    "scratchpad_size": size, "pool_block": True,
                    "transactions": list(self.mempool)[:MAX_BLOCK_TX],
                    "version": PROTOCOL, "miner_signature": "",
                    "threads_used": MAX_THREADS_PER_MINER
                }
                if verify_pow_sync(block, self.target):
                    return (await self.add_block(block, "pool"))[0]
                return False
            elif proof_int <= pool_target:
                self.pool_shares[addr] = self.pool_shares.get(addr, 0) + 1
                self.pool_total += 1
                return True
            return False

    def get_pool_template(self) -> Optional[dict]:
        now = time.time()
        if self.pool_template and (now - self.pool_template_ts) < 1.0:
            return self.pool_template
        if not self.chain:
            return None
        self.pool_template = {
            "height": self.height, "previous_hash": self.chain[-1]["hash"],
            "target": self.target, "pool_target": min(MAX_TARGET, int(self.target * POOL_DIFF_FACTOR)),
            "transactions": list(self.mempool)[:MAX_BLOCK_TX], "timestamp": int(now)
        }
        self.pool_template_ts = now
        return self.pool_template

    async def _notify(self, block: dict):
        if not self.ws_clients:
            return
        msg = json.dumps({"event": "new_block", "height": self.height,
                          "hash": block["hash"], "target": self.target,
                          "total_fees": block.get("total_fees", 0),
                          "reward": self.reward_at(block["index"])})
        active = {ws for ws in self.ws_clients if not ws.closed}
        dead = set()
        for ws in active:
            try:
                await ws.send_str(msg)
            except:
                dead.add(ws)
        self.ws_clients -= dead

    def get_stats(self) -> dict:
        return {
            "version": VERSION, "height": self.height, "difficulty": self.fmt_diff(),
            "total_supply": sum(self.accounts.values()) / COIN, "accounts": len(self.accounts),
            "peers": len(self.p2p.connections) if self.p2p else 0, "miners": len(self.ws_clients),
            "mempool": len(self.mempool), "transactions": self.total_tx, "blocks": self.accepted,
            "uptime": int(time.time() - self.start_time), "reward": self.reward_at(self.height) / COIN,
            "minimum_reward": MINIMUM_REWARD / COIN,
            "pool": {"shares": self.pool_total, "miners": len(self.pool_shares)},
            "burn": self.accounts.get(BURN_ADDR, 0) / COIN, "current_target": self.target,
            "dev_fund_active": True,
            "dev_fund_share": f"{DEV_FUND_SHARE}%",
            "chain": self.chain[-10:], "length": self.height
        }

    def get_address(self, addr: str) -> Optional[dict]:
        if not addr.startswith("RAM_"):
            return None
        return {"address": addr, "balance": self.accounts.get(addr, 0) / COIN,
                "nonce": self.nonces.get(addr, 0)}

    async def periodic_cleanup(self):
        while True:
            await asyncio.sleep(600)
            try:
                now = time.time()
                old = [h for h, b in self.orphans.items() if now - b.get('timestamp', 0) > 3600]
                for h in old:
                    del self.orphans[h]
                dead = {ws for ws in self.ws_clients if ws.closed}
                self.ws_clients -= dead
                gc.collect()
            except:
                pass


# ==================== P2P MANAGER ====================
class SecurePeerManager:
    def __init__(self, bc: Blockchain = None):
        self.bc = bc
        self.peers: Dict[str, PeerInfo] = {}
        self.connections: Dict[str, dict] = {}
        self.server = None
        self.running = False
        self.seed_registry = SeedRegistry()
        self.my_ip = MY_WHITE_IP
        self.node_type = IPUtils.detect_node_type(self.my_ip)
        self.rate_limiter = SecureRateLimiter()

    async def start_server(self, host: str, port: int):
        try:
            self.server = await asyncio.start_server(self._handle_connection, host, port)
            self.running = True
            log.info(f"🔒 P2P сервер: {host}:{port} | Тип: {self.node_type.upper()}")
            if self.node_type == NodeType.PUBLIC.value and self.bc:
                await self.seed_registry.add_seed(self.my_ip, P2P_PORT, self.bc.height, VERSION, self.node_type)
                log.info(f"🌟 SEED-нода: {self.my_ip}:{P2P_PORT}")
            for seed_dns in BOOTSTRAP_SEEDS:
                try:
                    ip = seed_dns.split(":")[0]
                    port_num = int(seed_dns.split(":")[1]) if ":" in seed_dns else P2P_PORT
                    if ip != self.my_ip:
                        asyncio.create_task(self._connect(ip, port_num))
                except:
                    pass
            asyncio.create_task(self._announce_loop())
            asyncio.create_task(self._cleanup_loop())
            asyncio.create_task(self._metrics_loop())
        except Exception as e:
            log.error(f"Ошибка P2P: {e}")

    async def _handle_connection(self, reader, writer):
        peername = writer.get_extra_info('peername')
        if not peername:
            writer.close()
            return
        addr = f"{peername[0]}:{peername[1]}"
        if not self.rate_limiter.check(addr):
            writer.close()
            return
        try:
            while self.running:
                data = await asyncio.wait_for(reader.readline(), timeout=PEER_TIMEOUT)
                if not data:
                    break
                try:
                    msg = json.loads(data.decode())
                    msg_type = msg.get("type", "")

                    if msg_type == "new_block" and self.bc:
                        block = msg.get("block")
                        if block:
                            await self.bc.add_block(block, addr)

                    elif msg_type == "get_peers":
                        peers = self.seed_registry.get_peers_for_exchange()
                        resp = json.dumps({"type": "peers", "peers": peers}) + "\n"
                        writer.write(resp.encode())
                        await writer.drain()

                    elif msg_type == "peers":
                        for peer in msg.get("peers", []):
                            ip = peer.get("ip", "")
                            port = peer.get("port", P2P_PORT)
                            if IPUtils.is_public_ip(ip) and ip != self.my_ip:
                                asyncio.create_task(self._connect(ip, port))

                    elif msg_type == "ping":
                        height = msg.get("height", 0)
                        version = msg.get("version", "")
                        node_type = msg.get("node_type", "private")
                        await self.seed_registry.update_peer_info(
                            peername[0], peername[1], height, version, node_type
                        )
                        resp = json.dumps({
                            "type": "pong", "height": self.bc.height if self.bc else 0,
                            "version": VERSION, "node_type": self.node_type
                        }) + "\n"
                        writer.write(resp.encode())
                        await writer.drain()

                except json.JSONDecodeError:
                    pass
                except:
                    pass
        except:
            pass
        finally:
            try:
                writer.close()
            except:
                pass

    async def _connect(self, ip: str, port: int):
        addr = f"{ip}:{port}"
        if addr in self.connections:
            return
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=5)
            self.connections[addr] = {"writer": writer, "reader": reader, "established": time.time()}
            CONNECTIONS_GAUGE.set(len(self.connections))

            ping_msg = json.dumps({
                "type": "ping", "height": self.bc.height if self.bc else 0,
                "version": VERSION, "node_type": self.node_type
            }) + "\n"
            writer.write(ping_msg.encode())
            await writer.drain()

            get_peers_msg = json.dumps({"type": "get_peers", "count": PEER_EXCHANGE_COUNT}) + "\n"
            writer.write(get_peers_msg.encode())
            await writer.drain()

            log.info(f"🔗 {addr}")
        except:
            pass

    async def _announce_loop(self):
        while self.running:
            await asyncio.sleep(ANNOUNCE_INTERVAL)
            if self.node_type == NodeType.PUBLIC.value and self.bc:
                await self.seed_registry.add_seed(self.my_ip, P2P_PORT, self.bc.height, VERSION, self.node_type)

            for addr, conn in list(self.connections.items()):
                try:
                    ping = json.dumps({
                        "type": "ping", "height": self.bc.height if self.bc else 0,
                        "version": VERSION, "node_type": self.node_type
                    }) + "\n"
                    conn["writer"].write(ping.encode())
                    await conn["writer"].drain()
                except:
                    self.connections.pop(addr, None)

    async def _cleanup_loop(self):
        while self.running:
            await asyncio.sleep(3600)
            await self.seed_registry.cleanup()
            self.rate_limiter.cleanup()
            now = time.time()
            dead = [a for a, c in self.connections.items() if now - c["established"] > PEER_TIMEOUT * 2]
            for addr in dead:
                try:
                    self.connections[addr]["writer"].close()
                except:
                    pass
                self.connections.pop(addr, None)

    async def _metrics_loop(self):
        while self.running:
            await asyncio.sleep(60)
            try:
                PEERS_GAUGE.set(len(self.peers))
                CONNECTIONS_GAUGE.set(len(self.connections))
                SEEDS_GAUGE.set(len(self.seed_registry.seeds))
                if self.bc:
                    HEIGHT_GAUGE.set(self.bc.height)
                    MEMPOOL_SIZE.set(len(self.bc.mempool))
            except:
                pass

    async def broadcast_block(self, block: dict):
        msg = json.dumps({"type": "new_block", "block": block}) + "\n"
        dead = []
        for addr, conn in list(self.connections.items()):
            try:
                conn["writer"].write(msg.encode())
                await conn["writer"].drain()
            except:
                dead.append(addr)
        for addr in dead:
            self.connections.pop(addr, None)
        CONNECTIONS_GAUGE.set(len(self.connections))

    async def stop(self):
        self.running = False
        for conn in self.connections.values():
            try:
                conn["writer"].close()
            except:
                pass
        if self.server:
            self.server.close()
            await self.server.wait_closed()


# ==================== API SECURITY ====================
class APISecurity:
    def __init__(self):
        self.rate_limiter = SecureRateLimiter()
        self.banned_ips: Dict[str, float] = {}

    def check(self, request) -> bool:
        ip = request.remote or "unknown"
        if ip in self.banned_ips and time.time() < self.banned_ips[ip]:
            API_REQUESTS.labels(endpoint=request.path, status="banned").inc()
            return False
        if not self.rate_limiter.check(f"api:{ip}", limit=API_RATE_LIMIT, window=60):
            self.banned_ips[ip] = time.time() + BAN_TIME
            API_REQUESTS.labels(endpoint=request.path, status="rate_limited").inc()
            return False
        return True


api_security = APISecurity()


# ==================== API HANDLERS ====================
def api_handler(func):
    @wraps(func)
    async def wrapper(request):
        if not api_security.check(request):
            return web.json_response({"error": "Too many requests"}, status=429)
        try:
            API_REQUESTS.labels(endpoint=request.path, status="ok").inc()
            return await func(request)
        except web.HTTPException:
            raise
        except Exception as e:
            log.error(f"API error {request.path}: {e}")
            API_REQUESTS.labels(endpoint=request.path, status="error").inc()
            return web.json_response({"error": str(e)}, status=500)
    return wrapper


def require_api_key(request):
    api_key = request.headers.get("X-API-Key", "")
    if api_key != API_KEY:
        API_REQUESTS.labels(endpoint=request.path, status="unauthorized").inc()
        raise web.HTTPUnauthorized(reason="Invalid API key")
    return True


@api_handler
async def handle_health(request):
    bc = request.app['bc']
    return web.json_response({
        "ok": True, "version": VERSION, "height": bc.height,
        "uptime": int(time.time() - bc.start_time),
        "peers": len(request.app['p2p'].connections),
        "mempool": len(bc.mempool)
    })

@api_handler
async def handle_chain(request):
    return web.json_response(request.app['bc'].get_stats())

@api_handler
async def handle_stats(request):
    return web.json_response(request.app['bc'].get_stats())

@api_handler
async def handle_block(request):
    bc = request.app['bc']
    try:
        i = int(request.match_info['idx'])
        if 0 <= i < len(bc.chain):
            return web.json_response(bc.chain[i])
    except:
        pass
    return web.json_response({"error": "not found"}, status=404)

@api_handler
async def handle_address(request):
    bc = request.app['bc']
    d = bc.get_address(request.match_info['addr'])
    return web.json_response(d) if d else web.json_response({"error": "invalid"}, status=400)

@api_handler
async def handle_pending(request):
    return web.json_response(list(request.app['bc'].mempool))

@api_handler
async def handle_top(request):
    bc = request.app['bc']
    lim = min(int(request.query.get("limit", 10)), 100)
    top = sorted(bc.accounts.items(), key=lambda x: x[1], reverse=True)[:lim]
    return web.json_response([{"address": a, "balance": b / COIN} for a, b in top])

@api_handler
async def handle_mine(request):
    try:
        require_api_key(request)
    except web.HTTPUnauthorized:
        raise
    bc = request.app['bc']
    try:
        d = await request.json()
    except:
        return web.json_response({"status": "rejected", "reason": "invalid json"}, status=400)
    if not isinstance(d, dict):
        return web.json_response({"status": "rejected", "reason": "invalid format"}, status=400)
    ok, why = await bc.add_block(d, request.remote)
    return web.json_response({"status": "ok" if ok else "rejected", "reason": why})

@api_handler
async def handle_tx(request):
    bc = request.app['bc']
    try:
        d = await request.json()
    except:
        return web.json_response({"status": "error", "reason": "invalid json"}, status=400)
    if not bc.verify_tx_signature(d):
        return web.json_response({"status": "rejected", "reason": "invalid signature"}, status=400)
    sender = d.get("sender", "")
    async with bc.mempool_lock:
        sig = d.get("signature", "")
        if sig in bc.mempool_hashes:
            return web.json_response({"status": "rejected", "reason": "duplicate tx"}, status=400)
        if bc.mempool_by_sender.get(sender, 0) >= MAX_MEMPOOL_PER_ADDRESS:
            return web.json_response({"status": "rejected", "reason": "too many pending tx"}, status=400)
        bc.mempool.append(d)
        bc.mempool_hashes.add(sig)
        bc.mempool_by_sender[sender] = bc.mempool_by_sender.get(sender, 0) + 1
    MEMPOOL_SIZE.set(len(bc.mempool))
    return web.json_response({"status": "ok"})

@api_handler
async def handle_pool_tmpl(request):
    bc = request.app['bc']
    t = bc.get_pool_template()
    return web.json_response(t) if t else web.json_response({"error": "no chain"}, status=503)

@api_handler
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

@api_handler
async def handle_pool_stats(request):
    bc = request.app['bc']
    return web.json_response({"shares": bc.pool_total, "miners": len(bc.pool_shares)})

@api_handler
async def handle_seeds(request):
    bc = request.app['bc']
    if bc.p2p:
        seeds = bc.p2p.seed_registry.get_active_seeds(100)
        return web.json_response({
            "seeds": [{"ip": s.ip, "port": s.port, "height": s.height,
                       "node_type": s.node_type} for s in seeds[:20]],
            "total": len(seeds)
        })
    return web.json_response({"seeds": [], "total": 0})

@api_handler
async def handle_network(request):
    bc = request.app['bc']
    p2p = bc.p2p
    return web.json_response({
        "my_ip": p2p.my_ip if p2p.node_type != NodeType.PRIVATE.value else "hidden",
        "node_type": p2p.node_type, "height": bc.height,
        "peers": len(p2p.connections),
        "active_seeds": len(p2p.seed_registry.get_active_seeds()),
        "seed_stats": p2p.seed_registry.get_stats()
    })

@api_handler
async def handle_coininfo(request):
    bc = request.app['bc']
    p2p = bc.p2p if bc.p2p else None
    return web.json_response({
        "name": "RAMCOIN", "symbol": "RAM",
        "algorithm": "Ramhash v7 (Memory-hard CPU)",
        "block_time": 30,
        "block_reward": bc.reward_at(bc.height) / COIN,
        "minimum_reward": MINIMUM_REWARD / COIN,
        "current_supply": sum(bc.accounts.values()) / COIN,
        "max_supply": "~17.5M + tail emission",
        "height": bc.height, "difficulty": bc.fmt_diff(),
        "peers": len(p2p.connections) if p2p else 0,
        "protocol": PROTOCOL, "version": VERSION, "halving": HALVING,
        "dev_fund_active": True,
        "dev_fund_share": f"{DEV_FUND_SHARE}%",
        "fixed_fee": FIXED_FEE / COIN
    })

@api_handler
async def handle_ws(request):
    bc = request.app['bc']
    ws = web.WebSocketResponse(heartbeat=30, timeout=60)
    await ws.prepare(request)
    bc.ws_clients.add(ws)
    log.info(f"🔌 WS клиент (всего: {len(bc.ws_clients)})")
    try:
        await ws.send_json({
            "event": "connected", "height": bc.height,
            "target": bc.target, "version": VERSION
        })
        async for m in ws:
            if m.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                break
    except:
        pass
    finally:
        bc.ws_clients.discard(ws)
    return ws


# ==================== NODE ====================
class Node:
    def __init__(self):
        self.p2p = SecurePeerManager()
        self.bc = Blockchain(self.p2p)
        self.p2p.bc = self.bc
        self.running = False

    async def start(self):
        self.running = True

        if not os.path.exists(API_KEY_FILE):
            with open(API_KEY_FILE, "w") as f:
                f.write(API_KEY)

        app = web.Application(client_max_size=MAX_REQUEST_SIZE)
        app['bc'] = self.bc
        app['p2p'] = self.p2p

        @web.middleware
        async def security_middleware(request, handler):
            if request.method == "OPTIONS":
                resp = web.Response(status=204)
            else:
                resp = await handler(request)
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
            resp.headers['X-Content-Type-Options'] = 'nosniff'
            resp.headers['X-Frame-Options'] = 'DENY'
            resp.headers['Server'] = 'RAMCOIN'
            return resp

        app.middlewares.append(security_middleware)

        app.router.add_get('/health', handle_health)
        app.router.add_get('/chain', handle_chain)
        app.router.add_get('/coininfo', handle_coininfo)
        app.router.add_get('/stats', handle_stats)
        app.router.add_get('/block/{idx}', handle_block)
        app.router.add_get('/address/{addr}', handle_address)
        app.router.add_get('/pending', handle_pending)
        app.router.add_get('/top', handle_top)
        app.router.add_post('/mine', handle_mine)
        app.router.add_post('/tx', handle_tx)
        app.router.add_get('/pool/template', handle_pool_tmpl)
        app.router.add_post('/pool/share', handle_pool_share)
        app.router.add_get('/pool/stats', handle_pool_stats)
        app.router.add_get('/seeds', handle_seeds)
        app.router.add_get('/network', handle_network)
        app.router.add_get('/ws', handle_ws)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", API_PORT)
        await site.start()

        try:
            start_http_server(METRICS_PORT)
            log.info(f"📊 Prometheus: http://0.0.0.0:{METRICS_PORT}")
        except:
            log.warning("⚠️ Prometheus не запущен (порт занят?)")

        log.info(f"🌐 API: http://0.0.0.0:{API_PORT}")
        log.info(f"🔑 API-Key: {API_KEY}")

        await self.p2p.start_server("0.0.0.0", P2P_PORT)

        log.info(f"""
╔════════════════════════════════════════════════════╗
║   RAMCOIN NODE v{VERSION} — GENESIS EDITION        ║
║   📍 IP: {self.p2p.my_ip} ({self.p2p.node_type.upper()})                         ║
║   📦 H: {self.bc.height}    💰 Reward: {self.bc.reward_at(self.bc.height) / COIN} RAM                 ║
║   🔒 Security: MAXIMUM                            ║
║   🌐 Peer Exchange: ON                            ║
║   ║   💱 Dev Fund: {DEV_FUND_SHARE}% (навсегда)          ║
║   ♾️  Tail Emission: {MINIMUM_REWARD / COIN} RAM                        ║
╚════════════════════════════════════════════════════╝
        """)

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_event_loop().add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:
                pass

        try:
            while self.running:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            log.info("⏹️ Остановка...")
        finally:
            await self.stop()

    async def stop(self):
        self.running = False
        await self.p2p.stop()
        log.info("👋 Нода остановлена")


async def main():
    log.info(f"🔐 API-Key сохранён в {API_KEY_FILE}")
    node = Node()
    await node.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bye")
    except Exception as e:
        log.critical(f"💥 FATAL: {e}")
        log.debug(traceback.format_exc())
        sys.exit(1)