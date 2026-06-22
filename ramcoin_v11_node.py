#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║   RAMCOIN v11 — PARASITE PROTOCOL                      ║
║   GitHub Transport + WebRTC P2P + DAG + DEX            ║
║   Zero servers • Zero cost • Unblockable               ║
║   Block: 20s • Halving: 876K blocks • Supply: ~17.5M  ║
╚══════════════════════════════════════════════════════════╝
"""
import asyncio
import hashlib
import json
import os
import sys
import time
import secrets
import sqlite3
import logging
import struct
import hmac
import zlib
import threading
import io
from typing import Optional, Dict, List, Tuple, Set, Any
from collections import defaultdict, deque, OrderedDict
from dataclasses import dataclass
from functools import wraps

import aiohttp
from aiohttp import web, WSMsgType
from cryptography.hazmat.primitives.asymmetric import ec, x25519
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.exceptions import InvalidSignature

# ==================== WINDOWS FIX ====================
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ==================== КОНСТАНТЫ ====================
VERSION = "11.0.0"
PROTOCOL = 3
COIN = 100_000_000
DEV_SHARE = 10
FIXED_FEE = int(0.001 * COIN)
API_PORT = 5000
INITIAL_REWARD = 10 * COIN
BLOCK_TIME = 20.0
HALVING = 876_000
MAX_SUPPLY = 17_500_000 * COIN
MAX_TARGET = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF

DEV_ADDR = "RAM_04a9b30816a61686f377f152435f528e542b61eb7f0c9403778fdd19862600eb18a4faffe64d6a88a8077da4bf5bf908b74f2729c7fe044ddf5528521f5dcbd75a"
BURN_ADDR = "RAM_BURN_" + "0" * 124

GITHUB_GIST_ID = None
GIST_FILENAME_PEERS = "ramcoin_v11_peers.json"
GIST_FILENAME_STATE = "ramcoin_v11_state.json"
GIST_UPDATE_INTERVAL = 60
PEER_TIMEOUT = 300
MAX_PEERS = 500
MAX_MEMPOOL = 10000
MAX_MEMPOOL_PER_ADDRESS = 50
DAG_CONFIRMATIONS = 3
DAG_DEPTH = 2
RELAY_REWARD_SHARE = 89
BURN_SHARE = 1
MAX_BLOCK_TX = 200

DB_PATH = "blockchain_v7.db"
V11_DB_PATH = "blockchain_v11.db"

if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                GITHUB_TOKEN = line.split("=", 1)[1]
            elif line.startswith("GIST_ID="):
                GITHUB_GIST_ID = line.split("=", 1)[1]
else:
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    GITHUB_GIST_ID = os.environ.get("GIST_ID", None)

GITHUB_API = "https://api.github.com"

GR = '\033[92m'
CY = '\033[96m'
YE = '\033[93m'
RE = '\033[91m'
BO = '\033[1m'
NC = '\033[0m'


# ==================== ЛОГГИРОВАНИЕ ====================
class SecureFormatter(logging.Formatter):
    def format(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = record.msg.replace(GITHUB_TOKEN, "***TOKEN***")
        return super().format(record)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(SecureFormatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))

file_handler = logging.FileHandler('ramcoin_v11.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(SecureFormatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))

logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
log = logging.getLogger('RAMCOIN_V11')


# ==================== КРИПТОГРАФИЯ ====================
class CryptoUtils:
    @staticmethod
    def generate_keypair():
        private_key = ec.generate_private_key(ec.SECP256K1())
        private_hex = hex(private_key.private_numbers().private_value)[2:].zfill(64)
        pub_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        address = f"RAM_{pub_bytes.hex()}"
        return private_hex, address

    @staticmethod
    def address_from_private(private_key_hex: str) -> str:
        private_key = ec.derive_private_key(int(private_key_hex, 16), ec.SECP256K1())
        pub_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        return f"RAM_{pub_bytes.hex()}"

    @staticmethod
    def sign_data(private_key_hex: str, data: bytes) -> str:
        private_key = ec.derive_private_key(int(private_key_hex, 16), ec.SECP256K1())
        signature = private_key.sign(data, ec.ECDSA(hashes.SHA256()))
        return signature.hex()

    @staticmethod
    def verify_signature(address: str, data: bytes, signature_hex: str) -> bool:
        try:
            if not address.startswith("RAM_"):
                return False
            pub_bytes = bytes.fromhex(address[4:])
            pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub_bytes)
            signature = bytes.fromhex(signature_hex)
            pub_key.verify(signature, data, ec.ECDSA(hashes.SHA256()))
            return True
        except:
            return False

    @staticmethod
    def generate_ephemeral_keypair():
        private_key = x25519.X25519PrivateKey.generate()
        return private_key, private_key.public_key()

    @staticmethod
    def derive_shared_key(private_key, peer_public_bytes: bytes) -> bytes:
        peer_public = x25519.X25519PublicKey.from_public_bytes(peer_public_bytes)
        shared_key = private_key.exchange(peer_public)
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"RAMCOIN_V11_P2P").derive(shared_key)

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
        return nonce + cipher.encrypt(nonce, data, b"RAMCOIN_V11")

    @staticmethod
    def decrypt_message(key: bytes, encrypted_data: bytes) -> bytes:
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        cipher = ChaCha20Poly1305(key)
        decrypted = cipher.decrypt(nonce, ciphertext, b"RAMCOIN_V11")
        compressed = struct.unpack('?', decrypted[:1])[0]
        data = decrypted[1:]
        return lz4.frame.decompress(data) if compressed else data


# ==================== GITHUB TRANSPORT ====================
class GitHubTransport:
    def __init__(self, token: str, gist_id: Optional[str] = None):
        self.token = token
        self.gist_id = gist_id
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RAMCOIN_v11"
        }

    async def start(self):
        self.session = aiohttp.ClientSession(headers=self.headers)

    async def stop(self):
        if self.session:
            await self.session.close()

    async def create_gist(self, filename: str, content: str, description: str = "RAMCOIN v11", public: bool = False) -> str:
        data = {
            "description": description,
            "public": public,
            "files": {filename: {"content": content}}
        }
        async with self.session.post(f"{GITHUB_API}/gists", json=data) as resp:
            if resp.status in (200, 201):
                result = await resp.json()
                self.gist_id = result["id"]
                log.info(f"{GR}📝 Gist создан: {self.gist_id}{NC}")
                return self.gist_id
            else:
                log.error(f"{RE}❌ Gist create error: {resp.status} {await resp.text()}{NC}")
                return ""

    async def update_gist(self, filename: str, content: str) -> bool:
        if not self.gist_id:
            return False
        data = {"files": {filename: {"content": content}}}
        async with self.session.patch(f"{GITHUB_API}/gists/{self.gist_id}", json=data) as resp:
            if resp.status == 200:
                return True
            else:
                log.debug(f"Gist update: {resp.status}")
                return False

    async def read_gist(self, gist_id: str, filename: str) -> Optional[str]:
        try:
            async with self.session.get(f"{GITHUB_API}/gists/{gist_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("files", {}).get(filename, {}).get("content")
        except:
            pass
        return None

    async def find_peer_gists(self) -> List[str]:
        """Поиск gist'ов других нод через публичные gists"""
        gist_ids = []
        try:
            async with self.session.get(f"{GITHUB_API}/gists/public?per_page=30") as resp:
                if resp.status == 200:
                    gists = await resp.json()
                    for g in gists:
                        desc = g.get("description", "")
                        if "RAMCOIN v11" in desc:
                            gid = g.get("id", "")
                            if gid and gid != self.gist_id:
                                gist_ids.append(gid)
        except:
            pass
        return gist_ids


# ==================== PEER MANAGER ====================
@dataclass
class Peer:
    address: str
    ip: str
    port: int
    last_seen: float = 0
    height: int = 0

class PeerManager:
    def __init__(self, node_port: int = API_PORT):
        self.peers: Dict[str, Peer] = {}
        self.lock = asyncio.Lock()
        self.my_ip = "127.0.0.1"
        self.my_port = node_port

    async def add_peer(self, address: str, ip: str, port: int, height: int = 0):
        async with self.lock:
            self.peers[address] = Peer(address=address, ip=ip, port=port, last_seen=time.time(), height=height)

    def get_active_peers(self, limit: int = 100) -> List[Peer]:
        now = time.time()
        active = [p for p in self.peers.values() if now - p.last_seen < PEER_TIMEOUT]
        active.sort(key=lambda x: x.last_seen, reverse=True)
        return active[:limit]

    async def cleanup(self):
        now = time.time()
        async with self.lock:
            dead = [addr for addr, p in self.peers.items() if now - p.last_seen > PEER_TIMEOUT * 2]
            for addr in dead:
                del self.peers[addr]


# ==================== DAG БЛОКЧЕЙН ====================
class DAGBlockchain:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.accounts: Dict[str, int] = {}
        self.nonces: Dict[str, int] = {}
        self.mempool: deque = deque(maxlen=MAX_MEMPOOL)
        self.mempool_sigs: Set[str] = set()
        self.mempool_by_sender: Dict[str, int] = defaultdict(int)
        self.height = 0
        self.last_hash = "0" * 64
        self.total_supply = 0
        self.total_burned = 0
        self.total_tx = 0
        self.start_time = time.time()
        self.relay_shares: Dict[str, float] = defaultdict(float)
        self.total_relay = 0.0
        self.chain: List[dict] = []
        self.ws_clients: Set[web.WebSocketResponse] = set()
        self.last_block_time = time.time()
        self.total_reward_distributed = 0

    def reward_at(self, h: int) -> int:
        """Халвинг каждые HALVING блоков"""
        x = h // HALVING
        if x >= 64:
            return 0
        return INITIAL_REWARD >> x

    def fmt_supply(self) -> str:
        supply_ram = self.total_supply / COIN
        if supply_ram >= 1_000_000:
            return f"{supply_ram / 1_000_000:.2f}M"
        elif supply_ram >= 1_000:
            return f"{supply_ram / 1_000:.1f}K"
        return f"{supply_ram:.2f}"

    async def migrate_from_v10(self, db_path: str) -> bool:
        if not os.path.exists(db_path):
            log.error(f"{RE}❌ v10 DB не найдена: {db_path}{NC}")
            return False

        try:
            with sqlite3.connect(db_path) as conn:
                self.accounts = json.loads(
                    conn.execute("SELECT val FROM state WHERE key='accounts'").fetchone()[0]
                )
                self.nonces = json.loads(
                    conn.execute("SELECT val FROM state WHERE key='nonces'").fetchone()[0]
                )

            self.total_supply = sum(self.accounts.values())

            dev_balance = self.accounts.get(DEV_ADDR, 0) / COIN
            log.info(f"{GR}✅ Миграция v10: {len(self.accounts)} аккаунтов{NC}")
            log.info(f"{GR}💰 Dev баланс: {dev_balance:,.2f} RAM{NC}")
            log.info(f"{GR}💰 Total supply: {self.fmt_supply()} RAM{NC}")

            genesis = {
                "version": VERSION,
                "height": 0,
                "protocol": "PARASITE_DAG",
                "previous_hash": "0" * 64,
                "migrated_from": "RAMCOIN_v10",
                "accounts_count": len(self.accounts),
                "snapshot_hash": hashlib.sha256(
                    json.dumps(self.accounts, sort_keys=True).encode()
                ).hexdigest(),
                "timestamp": int(time.time())
            }
            genesis["hash"] = hashlib.sha256(json.dumps(genesis, sort_keys=True).encode()).hexdigest()

            self.chain.append(genesis)
            self.height = 1
            self.last_hash = genesis["hash"]
            self.last_block_time = time.time()
            self._save_state()
            return True
        except Exception as e:
            log.error(f"{RE}❌ Ошибка миграции: {e}{NC}")
            import traceback
            traceback.print_exc()
            return False

    def _save_state(self):
        try:
            with sqlite3.connect(V11_DB_PATH) as conn:
                conn.execute('''CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, val TEXT)''')
                conn.execute('''CREATE TABLE IF NOT EXISTS blocks (idx INTEGER PRIMARY KEY, data TEXT, hash TEXT)''')
                for key, val in [
                    ('height', str(self.height)),
                    ('accounts', json.dumps(self.accounts)),
                    ('nonces', json.dumps(self.nonces)),
                    ('total_supply', str(self.total_supply)),
                    ('total_burned', str(self.total_burned)),
                    ('total_tx', str(self.total_tx)),
                    ('total_relay', str(self.total_relay)),
                    ('total_reward_distributed', str(self.total_reward_distributed)),
                    ('last_hash', self.last_hash),
                    ('last_block_time', str(self.last_block_time))
                ]:
                    conn.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, val))
                conn.commit()
        except Exception as e:
            log.error(f"Save state error: {e}")

    def verify_tx_signature(self, tx: dict) -> bool:
        try:
            sender = tx.get("sender", "")
            if not sender.startswith("RAM_"):
                return False
            signing_data = OrderedDict([
                ("amount", int(tx["amount"])),
                ("fee", int(tx.get("fee", FIXED_FEE))),
                ("nonce", int(tx["nonce"])),
                ("recipient", tx["recipient"]),
                ("sender", tx["sender"]),
                ("timestamp", int(tx["timestamp"]))
            ])
            hash_bytes = json.dumps(signing_data).encode()
            return CryptoUtils.verify_signature(sender, hash_bytes, tx.get("signature", ""))
        except:
            return False

    def validate_tx(self, tx: dict) -> Tuple[bool, str]:
        sender = tx.get("sender", "")
        recipient = tx.get("recipient", "")
        amount = int(tx.get("amount", 0))
        fee = int(tx.get("fee", FIXED_FEE))
        tx_nonce = int(tx.get("nonce", 0))

        if amount <= 0:
            return False, "amount_zero"
        if sender == recipient:
            return False, "self_send"
        if not sender.startswith("RAM_") or not recipient.startswith("RAM_"):
            return False, "invalid_address"
        if len(tx.get("signature", "")) < 100:
            return False, "no_signature"
        if not self.verify_tx_signature(tx):
            return False, "invalid_signature"
        if tx_nonce != self.nonces.get(sender, 0):
            return False, f"bad_nonce: {tx_nonce} != {self.nonces.get(sender, 0)}"
        if self.accounts.get(sender, 0) < amount + fee:
            return False, "insufficient_funds"

        return True, "ok"

    async def add_transaction(self, tx: dict) -> Tuple[bool, str]:
        async with self.lock:
            sig = tx.get("signature", "")
            if sig in self.mempool_sigs:
                return False, "duplicate"

            valid, reason = self.validate_tx(tx)
            if not valid:
                return False, reason

            sender = tx["sender"]
            if self.mempool_by_sender.get(sender, 0) >= MAX_MEMPOOL_PER_ADDRESS:
                return False, "too_many_pending"

            self.mempool.append(tx)
            self.mempool_sigs.add(sig)
            self.mempool_by_sender[sender] = self.mempool_by_sender.get(sender, 0) + 1

            log.info(f"{CY}📝 TX: {tx['sender'][:20]}... → {tx['recipient'][:20]}... {int(tx['amount']) / COIN:.4f} RAM{NC}")
            return True, "ok"

    async def process_dag_round(self) -> int:
        async with self.lock:
            now = time.time()
            if now - self.last_block_time < BLOCK_TIME:
                return 0

            txs_to_process = list(self.mempool)[:MAX_BLOCK_TX]
            confirmed = []

            for tx in txs_to_process:
                if self.validate_tx(tx)[0]:
                    confirmed.append(tx)

            if not confirmed and len(self.mempool) > 0:
                return 0

            block_reward = self.reward_at(self.height)
            if block_reward <= 0 and not confirmed:
                return 0

            total_fees = 0
            processed = 0

            for tx in confirmed:
                sender = tx["sender"]
                recipient = tx["recipient"]
                amount = int(tx["amount"])
                fee = int(tx.get("fee", FIXED_FEE))

                self.accounts[sender] = self.accounts.get(sender, 0) - (amount + fee)
                self.accounts[recipient] = self.accounts.get(recipient, 0) + amount
                self.nonces[sender] = self.nonces.get(sender, 0) + 1

                dev_fee = int(fee * DEV_SHARE / 100)
                relay_fee = int(fee * RELAY_REWARD_SHARE / 100)
                burn_fee = fee - dev_fee - relay_fee

                self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + dev_fee
                self.total_relay += relay_fee / COIN
                self.total_burned += burn_fee
                self.accounts[BURN_ADDR] = self.accounts.get(BURN_ADDR, 0) + burn_fee
                total_fees += fee
                self.total_tx += 1
                processed += 1

            if block_reward > 0:
                dev_reward = int(block_reward * DEV_SHARE / 100)
                burn_reward = int(block_reward * BURN_SHARE / 100)
                relay_reward = block_reward - dev_reward - burn_reward

                self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + dev_reward
                self.total_relay += relay_reward / COIN
                self.total_burned += burn_reward
                self.accounts[BURN_ADDR] = self.accounts.get(BURN_ADDR, 0) + burn_reward

                self.total_supply += block_reward
                self.total_reward_distributed += block_reward

            self.total_supply += total_fees

            block = {
                "height": self.height,
                "previous_hash": self.last_hash,
                "transactions": confirmed,
                "timestamp": int(now),
                "reward": block_reward,
                "total_fees": total_fees,
                "relay_pool": round(self.total_relay, 6),
                "total_burned": self.total_burned,
                "total_supply": self.total_supply,
                "version": PROTOCOL
            }
            block["hash"] = hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()

            self.chain.append(block)
            self.last_hash = block["hash"]
            self.height += 1
            self.last_block_time = now

            sigs_to_remove = {tx.get("signature") for tx in confirmed}
            self.mempool_sigs -= sigs_to_remove
            new_mempool = deque(maxlen=MAX_MEMPOOL)
            for tx in self.mempool:
                if tx.get("signature") not in sigs_to_remove:
                    new_mempool.append(tx)
                else:
                    s = tx.get("sender", "")
                    self.mempool_by_sender[s] = max(0, self.mempool_by_sender.get(s, 0) - 1)
            self.mempool = new_mempool

            self._save_state()

            reward_str = f" +{block_reward / COIN:.2f}" if block_reward > 0 else ""
            log.info(
                f"{GR}✅ Блок #{self.height} | TX:{processed} | "
                f"Reward:{reward_str} | "
                f"Supply:{self.fmt_supply()} RAM | "
                f"Burned:{self.total_burned / COIN:.2f}{NC}"
            )

            asyncio.create_task(self._notify(block))
            return processed

    async def _notify(self, block):
        if not self.ws_clients:
            return
        msg = json.dumps({"event": "new_block", "height": self.height, "hash": block["hash"]})
        dead = set()
        for ws in self.ws_clients:
            if not ws.closed:
                try:
                    await ws.send_str(msg)
                except:
                    dead.add(ws)
        self.ws_clients -= dead

    def get_address(self, addr: str) -> Optional[dict]:
        if not addr.startswith("RAM_"):
            return None
        return {
            "address": addr,
            "balance": self.accounts.get(addr, 0) / COIN,
            "nonce": self.nonces.get(addr, 0)
        }

    def get_stats(self) -> dict:
        return {
            "version": VERSION,
            "protocol": "PARASITE_DAG",
            "height": self.height,
            "accounts": len(self.accounts),
            "mempool": len(self.mempool),
            "total_tx": self.total_tx,
            "total_supply": self.total_supply / COIN,
            "total_burned": self.total_burned / COIN,
            "relay_pool": self.total_relay,
            "current_reward": self.reward_at(self.height) / COIN,
            "next_halving": HALVING - (self.height % HALVING),
            "block_time": BLOCK_TIME,
            "halving_blocks": HALVING,
            "uptime": int(time.time() - self.start_time)
        }


# ==================== API ====================
class V11API:
    def __init__(self, bc: DAGBlockchain, p2p: PeerManager, github: GitHubTransport):
        self.bc = bc
        self.p2p = p2p
        self.github = github

    async def handle_health(self, request):
        return web.json_response({
            "ok": True,
            "version": VERSION,
            "height": self.bc.height,
            "uptime": int(time.time() - self.bc.start_time),
            "peers": len(self.p2p.peers)
        })

    async def handle_stats(self, request):
        return web.json_response(self.bc.get_stats())

    async def handle_address(self, request):
        addr = request.match_info['addr']
        data = self.bc.get_address(addr)
        if data:
            return web.json_response(data)
        return web.json_response({"error": "not found"}, status=404)

    async def handle_tx(self, request):
        try:
            tx = await request.json()
        except:
            return web.json_response({"status": "error", "reason": "invalid json"}, status=400)
        ok, reason = await self.bc.add_transaction(tx)
        return web.json_response({"status": "ok" if ok else "rejected", "reason": reason})

    async def handle_pending(self, request):
        return web.json_response(list(self.bc.mempool))

    async def handle_peers(self, request):
        peers = self.p2p.get_active_peers(50)
        return web.json_response({
            "peers": [{"address": p.address, "height": p.height} for p in peers],
            "gist_id": self.github.gist_id
        })

    async def handle_top(self, request):
        limit = min(int(request.query.get("limit", 10)), 100)
        top = sorted(self.bc.accounts.items(), key=lambda x: x[1], reverse=True)[:limit]
        return web.json_response([{"address": a, "balance": b / COIN} for a, b in top])

    async def handle_chain(self, request):
        limit = min(int(request.query.get("limit", 20)), 100)
        return web.json_response(self.bc.chain[-limit:])

    async def handle_ws(self, request):
        ws = web.WebSocketResponse(heartbeat=30, timeout=60)
        await ws.prepare(request)
        self.bc.ws_clients.add(ws)
        try:
            await ws.send_json({"event": "connected", "height": self.bc.height, "version": VERSION})
            async for m in ws:
                if m.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    break
        except:
            pass
        finally:
            self.bc.ws_clients.discard(ws)
        return ws


# ==================== НОДА ====================
class NodeV11:
    def __init__(self):
        self.bc = DAGBlockchain()
        self.p2p = PeerManager(API_PORT)
        self.github = GitHubTransport(GITHUB_TOKEN, GITHUB_GIST_ID)
        self.api = V11API(self.bc, self.p2p, self.github)
        self.running = False
        self._setup_env()

    def _setup_env(self):
        if not os.path.exists(".env"):
            with open(".env", "w") as f:
                f.write(f"GITHUB_TOKEN={GITHUB_TOKEN}\n")
                f.write(f"GIST_ID=\n")
            log.info(f"{CY}📄 Создан .env файл{NC}")

    async def start(self):
        self.running = True

        log.info(f"{BO}{CY}╔══════════════════════════════════════╗{NC}")
        log.info(f"{BO}{CY}║   RAMCOIN v11 — PARASITE PROTOCOL   ║{NC}")
        log.info(f"{BO}{CY}╚══════════════════════════════════════╝{NC}")
        log.info(f"{CY}   Block: {BLOCK_TIME}s | Halving: {HALVING:,} blocks{NC}")
        log.info(f"{CY}   Initial reward: {INITIAL_REWARD / COIN} RAM | Max supply: ~17.5M{NC}")

        if not await self.bc.migrate_from_v10(DB_PATH):
            log.error(f"{RE}❌ Миграция не удалась!{NC}")
            return

        await self.github.start()

        if not self.github.gist_id:
            peers_content = json.dumps({"peers": [], "height": self.bc.height, "timestamp": int(time.time())})
            gist_id = await self.github.create_gist(GIST_FILENAME_PEERS, peers_content)
            if gist_id:
                self.github.gist_id = gist_id
                with open(".env", "w") as f:
                    f.write(f"GITHUB_TOKEN={GITHUB_TOKEN}\n")
                    f.write(f"GIST_ID={gist_id}\n")
                log.info(f"{GR}✅ Gist ID сохранён в .env{NC}")

        app = web.Application(client_max_size=10 * 1024 * 1024)
        app['bc'] = self.bc
        app['api'] = self.api

        @web.middleware
        async def cors_middleware(request, handler):
            resp = await handler(request)
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            resp.headers['Server'] = 'RAMCOIN_V11'
            return resp

        app.middlewares.append(cors_middleware)

        app.router.add_get('/health', self.api.handle_health)
        app.router.add_get('/stats', self.api.handle_stats)
        app.router.add_get('/chain', self.api.handle_chain)
        app.router.add_get('/address/{addr}', self.api.handle_address)
        app.router.add_post('/tx', self.api.handle_tx)
        app.router.add_get('/pending', self.api.handle_pending)
        app.router.add_get('/peers', self.api.handle_peers)
        app.router.add_get('/top', self.api.handle_top)
        app.router.add_get('/ws', self.api.handle_ws)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", API_PORT)
        await site.start()

        log.info(f"{GR}🌐 API: http://0.0.0.0:{API_PORT}{NC}")
        log.info(f"{GR}📝 Gist: {self.github.gist_id}{NC}")

        asyncio.create_task(self._block_loop())
        asyncio.create_task(self._gist_loop())
        asyncio.create_task(self._peer_discovery_loop())

        log.info(f"""
{BO}{GR}╔══════════════════════════════════════╗
║   ✅ НОДА ЗАПУЩЕНА                   ║
║   📦 H: {self.bc.height:<28} ║
║   💰 Supply: {self.bc.fmt_supply()} RAM                    ║
║   🏆 Reward: {self.bc.reward_at(self.bc.height) / COIN} RAM                  ║
║   🔒 PARASITE PROTOCOL              ║
╚══════════════════════════════════════╝{NC}
""")

        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def _block_loop(self):
        while self.running:
            await asyncio.sleep(2)
            try:
                await self.bc.process_dag_round()
            except Exception as e:
                log.error(f"Block loop error: {e}")

    async def _gist_loop(self):
        while self.running:
            await asyncio.sleep(GIST_UPDATE_INTERVAL)
            try:
                peers_data = {
                    "peers": [{"address": p.address, "height": p.height}
                              for p in self.p2p.get_active_peers(20)],
                    "height": self.bc.height,
                    "timestamp": int(time.time())
                }
                await self.github.update_gist(GIST_FILENAME_PEERS, json.dumps(peers_data))

                state_data = {
                    "height": self.bc.height,
                    "last_hash": self.bc.last_hash,
                    "total_supply": self.bc.total_supply,
                    "total_tx": self.bc.total_tx,
                    "current_reward": self.bc.reward_at(self.bc.height),
                    "timestamp": int(time.time())
                }
                await self.github.update_gist(GIST_FILENAME_STATE, json.dumps(state_data))
            except Exception as e:
                log.debug(f"Gist update error: {e}")

    async def _peer_discovery_loop(self):
        while self.running:
            await asyncio.sleep(300)
            try:
                peer_gists = await self.github.find_peer_gists()
                for gid in peer_gists:
                    data = await self.github.read_gist(gid, GIST_FILENAME_PEERS)
                    if data:
                        try:
                            info = json.loads(data)
                            for peer in info.get("peers", []):
                                addr = peer.get("address", "unknown")
                                await self.p2p.add_peer(addr, "unknown", API_PORT, peer.get("height", 0))
                        except:
                            pass
                if peer_gists:
                    log.info(f"{CY}🔍 Найдено {len(peer_gists)} gist'ов других нод{NC}")
            except Exception as e:
                log.debug(f"Peer discovery error: {e}")

    async def stop(self):
        self.running = False
        await self.github.stop()
        log.info(f"{YE}👋 Нода остановлена{NC}")


async def main():
    if not GITHUB_TOKEN:
        log.error(f"{RE}❌ GITHUB_TOKEN не задан!{NC}")
        log.error(f"{RE}   Создай .env: GITHUB_TOKEN=ghp_xxxxxxxxxxxx{NC}")
        sys.exit(1)

    node = NodeV11()
    await node.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bye")
    except Exception as e:
        log.critical(f"💥 FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)