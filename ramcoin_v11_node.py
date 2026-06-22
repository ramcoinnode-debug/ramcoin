#!/usr/bin/env python3
"""
RAMCOIN v11 - PARASITE PROTOCOL
Full node + API + Relay rewards + P2P gossip + Wallet binding
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
import zlib
import io
import random
from typing import Optional, Dict, List, Tuple, Set, Any
from collections import defaultdict, deque, OrderedDict

import aiohttp
from aiohttp import web, WSMsgType
from cryptography.hazmat.primitives.asymmetric import ec, x25519
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

VERSION = "11.2.1"
PROTOCOL = 3
COIN = 100_000_000
DEV_SHARE = 10
BURN_SHARE = 1
RELAY_SHARE = 89
FIXED_FEE = int(0.001 * COIN)
API_PORT = 5000
INITIAL_REWARD = 10 * COIN
BLOCK_TIME = 20.0
HALVING = 876_000
RELAY_DISTRIBUTION_INTERVAL = 100

GIST_SEARCH_INTERVAL = 300
GIST_UPDATE_INTERVAL = 120
GOSSIP_INTERVAL = 30
MAX_GIST_REQUESTS_PER_HOUR = 100

DEV_ADDR = "RAM_04a9b30816a61686f377f152435f528e542b61eb7f0c9403778fdd19862600eb18a4faffe64d6a88a8077da4bf5bf908b74f2729c7fe044ddf5528521f5dcbd75a"
BURN_ADDR = "RAM_BURN_" + "0" * 124

GITHUB_API = "https://api.github.com"
GIST_DESC = "RAMCOIN v11"
GIST_PEERS = "ramcoin_v11_peers.json"
GIST_STATE = "ramcoin_v11_state.json"

DB_V10 = "blockchain_v7.db"
DB_V11 = "blockchain_v11.db"
WALLET_ADDR_FILE = "wallet_address.txt"

C_GREEN = '\033[92m'
C_CYAN = '\033[96m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_BOLD = '\033[1m'
C_RESET = '\033[0m'
C_BLUE = '\033[94m'
C_MAGENTA = '\033[95m'
C_WHITE = '\033[97m'
C_DIM = '\033[2m'

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_GIST_ID = os.environ.get("GIST_ID", "")

if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                GITHUB_TOKEN = line.split("=", 1)[1].strip()
            elif line.startswith("GIST_ID="):
                GITHUB_GIST_ID = line.split("=", 1)[1].strip()

HAS_TOKEN = bool(GITHUB_TOKEN)
HAS_V10 = os.path.exists(DB_V10)

MY_ADDRESS = ""
if os.path.exists(WALLET_ADDR_FILE):
    with open(WALLET_ADDR_FILE, "r") as f:
        MY_ADDRESS = f.read().strip()


def get_address():
    global MY_ADDRESS
    if MY_ADDRESS and MY_ADDRESS.startswith("RAM_"):
        return MY_ADDRESS

    print(f"\n{C_YELLOW}No wallet linked to this node.{C_RESET}")
    print(f"1. Create a new wallet")
    print(f"2. Enter existing RAM address")
    c = input("Choose [1/2]: ").strip()

    if c == "1":
        private_key = ec.generate_private_key(ec.SECP256K1())
        priv_hex = hex(private_key.private_numbers().private_value)[2:].zfill(64)
        pub_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        addr = f"RAM_{pub_bytes.hex()}"
        print(f"\n{C_GREEN}Wallet created!{C_RESET}")
        print(f"{C_BOLD}Address: {addr}{C_RESET}")
        print(f"{C_YELLOW}SAVE YOUR PRIVATE KEY:{C_RESET} {priv_hex}")
        print(f"{C_YELLOW}This key is NOT stored by the node. Save it manually!{C_RESET}")
        input("\nPress ENTER to continue...")
        MY_ADDRESS = addr
    elif c == "2":
        addr = input("Enter RAM address: ").strip()
        if addr.startswith("RAM_") and len(addr) == 134:
            MY_ADDRESS = addr
            print(f"{C_GREEN}Address linked: {addr[:30]}...{C_RESET}")
        else:
            print(f"{C_RED}Invalid address!{C_RESET}")
            return get_address()
    else:
        MY_ADDRESS = DEV_ADDR
        print(f"{C_YELLOW}Using default address.{C_RESET}")

    with open(WALLET_ADDR_FILE, "w") as f:
        f.write(MY_ADDRESS)
    return MY_ADDRESS


class ColoredFormatter(logging.Formatter):
    COLORS = {
        'INFO': C_CYAN,
        'WARNING': C_YELLOW,
        'ERROR': C_RED,
        'CRITICAL': C_RED + C_BOLD,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, C_RESET)
        record.levelname = f"{color}{record.levelname}{C_RESET}"
        return super().format(record)


log = logging.getLogger('RAMCOIN')
log.setLevel(logging.INFO)
h = logging.StreamHandler(sys.stdout)
h.setFormatter(ColoredFormatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
log.addHandler(h)


class CryptoUtils:
    @staticmethod
    def verify_sig(address: str, data: bytes, sig_hex: str) -> bool:
        try:
            if not address.startswith("RAM_"):
                return False
            pub_bytes = bytes.fromhex(address[4:])
            pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub_bytes)
            pub_key.verify(bytes.fromhex(sig_hex), data, ec.ECDSA(hashes.SHA256()))
            return True
        except:
            return False


class GitHubClient:
    def __init__(self):
        self.session = None
        self.gist_id = GITHUB_GIST_ID if HAS_TOKEN else ""
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RAMCOIN_v11"
        }
        if HAS_TOKEN:
            self.headers["Authorization"] = f"token {GITHUB_TOKEN}"
        self.request_count = 0
        self.hour_start = time.time()

    async def start(self):
        self.session = aiohttp.ClientSession(headers=self.headers)

    async def stop(self):
        if self.session:
            await self.session.close()

    def _check_limit(self):
        now = time.time()
        if now - self.hour_start > 3600:
            self.request_count = 0
            self.hour_start = now
        if self.request_count >= MAX_GIST_REQUESTS_PER_HOUR:
            return False
        self.request_count += 1
        return True

    async def _get(self, url):
        if not self._check_limit():
            return None
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    return await r.json()
        except:
            pass
        return None

    async def _patch(self, url, data):
        if not self._check_limit():
            return False
        try:
            async with self.session.patch(url, json=data, timeout=aiohttp.ClientTimeout(total=10)) as r:
                return r.status == 200
        except:
            return False

    async def _post(self, url, data):
        if not self._check_limit():
            return None
        try:
            async with self.session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status in (200, 201):
                    return await r.json()
        except:
            pass
        return None

    async def create_gist(self, filename, content):
        if not HAS_TOKEN:
            return None
        data = {"description": GIST_DESC, "public": False, "files": {filename: {"content": content}}}
        result = await self._post(f"{GITHUB_API}/gists", data)
        return result.get("id") if result else None

    async def update_gist(self, filename, content):
        if not HAS_TOKEN or not self.gist_id:
            return False
        return await self._patch(f"{GITHUB_API}/gists/{self.gist_id}", {"files": {filename: {"content": content}}})

    async def read_gist(self, gist_id, filename):
        data = await self._get(f"{GITHUB_API}/gists/{gist_id}")
        if data and isinstance(data, dict):
            files = data.get("files", {})
            if isinstance(files, dict):
                f = files.get(filename, {})
                if isinstance(f, dict):
                    return f.get("content")
        return None

    async def find_peers(self):
        ids = []
        data = await self._get(f"{GITHUB_API}/gists/public?per_page=30")
        if data and isinstance(data, list):
            for g in data:
                if isinstance(g, dict):
                    desc = g.get("description") or ""
                    gid = g.get("id") or ""
                    if GIST_DESC in str(desc) and gid and gid != self.gist_id:
                        ids.append(gid)
        return ids

    async def download_chain(self, peer_url):
        data = await self._get(f"{peer_url}/chain?limit=5000")
        return data if data and isinstance(data, list) else []

    async def get_peers_from_node(self, peer_url):
        data = await self._get(f"{peer_url}/peers")
        return data if data and isinstance(data, dict) else {}


class PeerManager:
    def __init__(self):
        self.peers = {}
        self.lock = asyncio.Lock()

    async def add(self, addr, height=0):
        async with self.lock:
            self.peers[addr] = {"height": height, "last_seen": time.time()}

    async def update(self, addr, height):
        async with self.lock:
            if addr in self.peers:
                self.peers[addr]["height"] = height
                self.peers[addr]["last_seen"] = time.time()
            else:
                self.peers[addr] = {"height": height, "last_seen": time.time()}

    def get_active(self, limit=100):
        now = time.time()
        active = [(a, p) for a, p in self.peers.items() if now - p["last_seen"] < 600]
        active.sort(key=lambda x: x[1]["last_seen"], reverse=True)
        return active[:limit]

    def count(self):
        return len(self.peers)


class Blockchain:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.accounts = {}
        self.nonces = {}
        self.mempool = deque(maxlen=10000)
        self.mempool_sigs = set()
        self.mempool_count = defaultdict(int)
        self.height = 0
        self.last_hash = "0" * 64
        self.total_supply = 0
        self.total_burned = 0
        self.total_tx = 0
        self.start_time = time.time()
        self.total_relay = 0.0
        self.total_dev_reward = 0.0
        self.total_burn_reward = 0.0
        self.total_relay_reward = 0.0
        self.total_fees_collected = 0
        self.chain = []
        self.ws_clients = set()
        self.last_block_time = time.time()
        self.synced = False
        self.relay_data_served = defaultdict(int)
        self.relay_balances = defaultdict(float)
        self.total_relay_distributed = 0.0
        self.relay_addresses = defaultdict(str)

    def reward_at(self, h):
        x = h // HALVING
        return 0 if x >= 64 else INITIAL_REWARD >> x

    def fmt(self, n):
        if n >= 1_000_000:
            return f"{n / 1_000_000:.2f}M"
        elif n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return f"{n:,.2f}"

    async def init(self, github):
        if HAS_V10:
            await self._migrate()
        else:
            await self._genesis()
        await self._sync(github)

    async def _migrate(self):
        try:
            with sqlite3.connect(DB_V10) as conn:
                self.accounts = json.loads(conn.execute("SELECT val FROM state WHERE key='accounts'").fetchone()[0])
                self.nonces = json.loads(conn.execute("SELECT val FROM state WHERE key='nonces'").fetchone()[0])
            self.total_supply = sum(self.accounts.values())
            log.info(f"{C_GREEN}Migration OK: {len(self.accounts)} accounts{C_RESET}")
            log.info(f"  Dev: {C_BOLD}{self.accounts.get(DEV_ADDR, 0) / COIN:,.2f} RAM{C_RESET}")
            log.info(f"  Supply: {C_BOLD}{self.total_supply / COIN:,.2f} RAM{C_RESET}")
        except Exception as e:
            log.error(f"Migration failed: {e}")
            await self._genesis()
            return
        g = {"height": 0, "previous_hash": "0" * 64, "protocol": "PARASITE", "migrated_from": "v10",
             "timestamp": int(time.time())}
        g["hash"] = hashlib.sha256(json.dumps(g, sort_keys=True).encode()).hexdigest()
        self.chain.append(g)
        self.height = 1
        self.last_hash = g["hash"]
        self.last_block_time = time.time()
        self._save()

    async def _genesis(self):
        g = {"height": 0, "previous_hash": "0" * 64, "protocol": "PARASITE", "timestamp": int(time.time())}
        g["hash"] = hashlib.sha256(json.dumps(g, sort_keys=True).encode()).hexdigest()
        self.chain.append(g)
        self.height = 1
        self.last_hash = g["hash"]
        self.last_block_time = time.time()
        log.info(f"{C_CYAN}Fresh genesis created{C_RESET}")

    async def _sync(self, github):
        gists = await github.find_peers()
        if github.gist_id:
            gists.insert(0, github.gist_id)
        if not gists:
            self.synced = True
            return
        urls = set()
        for gid in gists[:5]:
            d = await github.read_gist(gid, GIST_PEERS)
            if d:
                try:
                    info = json.loads(d)
                    if isinstance(info, dict):
                        for p in info.get("peers", []):
                            addr = p.get("address", "")
                            if addr:
                                urls.add(f"http://{addr}")
                except:
                    pass
        for url in list(urls)[:3]:
            try:
                chain = await github.download_chain(url)
                if chain and len(chain) > self.height:
                    for blk in chain:
                        if isinstance(blk, dict) and blk.get("height", 0) >= self.height:
                            await self._apply(blk)
                    log.info(f"{C_GREEN}Synced {len(chain)} blocks{C_RESET}")
                    self.synced = True
                    return
            except:
                pass
        self.synced = True

    async def _apply(self, blk):
        async with self.lock:
            bh = blk.get("height", 0)
            if bh < self.height:
                return
            for tx in blk.get("transactions", []):
                if isinstance(tx, dict) and self._verify_tx(tx):
                    s, r, a = tx.get("sender", ""), tx.get("recipient", ""), int(tx.get("amount", 0))
                    f = int(tx.get("fee", FIXED_FEE))
                    if self.accounts.get(s, 0) >= a + f:
                        self.accounts[s] = self.accounts.get(s, 0) - (a + f)
                        self.accounts[r] = self.accounts.get(r, 0) + a
                        self.nonces[s] = self.nonces.get(s, 0) + 1
                        df = int(f * DEV_SHARE / 100)
                        rf = int(f * RELAY_SHARE / 100)
                        bf = f - df - rf
                        self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + df
                        self.total_relay += rf / COIN
                        self.total_burned += bf
                        self.accounts[BURN_ADDR] = self.accounts.get(BURN_ADDR, 0) + bf
                        self.total_tx += 1
            rw = self.reward_at(bh)
            if rw > 0:
                dr = int(rw * DEV_SHARE / 100)
                br = int(rw * BURN_SHARE / 100)
                rr = rw - dr - br
                self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + dr
                self.total_relay += rr / COIN
                self.total_burned += br
                self.accounts[BURN_ADDR] = self.accounts.get(BURN_ADDR, 0) + br
                self.total_supply += rw
                self.total_dev_reward += dr
                self.total_burn_reward += br
                self.total_relay_reward += rr
            self.chain.append(blk)
            self.height = max(self.height, bh + 1)
            self.last_hash = blk.get("hash", self.last_hash)
            self.last_block_time = time.time()

    def _verify_tx(self, tx):
        try:
            data = OrderedDict([
                ("amount", int(tx["amount"])), ("fee", int(tx.get("fee", FIXED_FEE))),
                ("nonce", int(tx["nonce"])), ("recipient", tx["recipient"]),
                ("sender", tx["sender"]), ("timestamp", int(tx["timestamp"]))
            ])
            return CryptoUtils.verify_sig(tx["sender"], json.dumps(data).encode(), tx.get("signature", ""))
        except:
            return False

    def check_tx(self, tx):
        s = tx.get("sender", "")
        r = tx.get("recipient", "")
        a = int(tx.get("amount", 0))
        f = int(tx.get("fee", FIXED_FEE))
        n = int(tx.get("nonce", 0))
        if a <= 0: return False, "amount_zero"
        if s == r: return False, "self_send"
        if not s.startswith("RAM_") or not r.startswith("RAM_"): return False, "invalid_address"
        if not self._verify_tx(tx): return False, "invalid_signature"
        if n != self.nonces.get(s, 0): return False, "bad_nonce"
        if self.accounts.get(s, 0) < a + f: return False, "insufficient_funds"
        return True, "ok"

    async def add_tx(self, tx):
        async with self.lock:
            sig = tx.get("signature", "")
            if sig in self.mempool_sigs: return False, "duplicate"
            ok, why = self.check_tx(tx)
            if not ok: return False, why
            s = tx["sender"]
            if self.mempool_count.get(s, 0) >= 50: return False, "too_many"
            self.mempool.append(tx)
            self.mempool_sigs.add(sig)
            self.mempool_count[s] = self.mempool_count.get(s, 0) + 1
            return True, "ok"

    def record_relay(self, peer_addr: str, bytes_served: int):
        self.relay_data_served[peer_addr] += bytes_served

    def link_address(self, peer_id: str, ram_address: str):
        self.relay_addresses[peer_id] = ram_address

    def distribute_relay_pool(self):
        total_served = sum(self.relay_data_served.values())
        if total_served <= 0 or self.total_relay <= 0:
            return

        distributed = 0.0
        nodes_paid = 0
        for peer_id, served in self.relay_data_served.items():
            if served > 0:
                share = (served / total_served) * self.total_relay
                ram_addr = self.relay_addresses.get(peer_id, peer_id)
                if ram_addr.startswith("RAM_"):
                    self.relay_balances[ram_addr] += share
                    self.accounts[ram_addr] = self.accounts.get(ram_addr, 0) + int(share * COIN)
                distributed += share
                nodes_paid += 1

        self.total_relay_distributed += distributed
        self.total_relay = 0.0
        self.relay_data_served.clear()
        log.info(f"{C_BLUE}  >> Relay pool distributed: {self.fmt(distributed)} RAM to {nodes_paid} nodes{C_RESET}")

    async def make_block(self):
        async with self.lock:
            now = time.time()
            if now - self.last_block_time < BLOCK_TIME:
                return None
            txs = [tx for tx in list(self.mempool)[:200] if self.check_tx(tx)[0]]
            rw = self.reward_at(self.height)
            if rw <= 0 and not txs:
                return None

            block_fees = block_fee_dev = block_fee_relay = block_fee_burn = 0

            for tx in txs:
                s, r, a = tx["sender"], tx["recipient"], int(tx["amount"])
                f = int(tx.get("fee", FIXED_FEE))
                self.accounts[s] = self.accounts.get(s, 0) - (a + f)
                self.accounts[r] = self.accounts.get(r, 0) + a
                self.nonces[s] = self.nonces.get(s, 0) + 1
                df = int(f * DEV_SHARE / 100)
                rf = int(f * RELAY_SHARE / 100)
                bf = f - df - rf
                self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + df
                self.total_relay += rf / COIN
                self.total_burned += bf
                self.accounts[BURN_ADDR] = self.accounts.get(BURN_ADDR, 0) + bf
                block_fees += f
                block_fee_dev += df
                block_fee_relay += rf
                block_fee_burn += bf
                self.total_tx += 1
                self.total_fees_collected += f

            block_dev = block_burn = block_relay = 0
            if rw > 0:
                dr = int(rw * DEV_SHARE / 100)
                br = int(rw * BURN_SHARE / 100)
                rr = rw - dr - br
                self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + dr
                self.total_relay += rr / COIN
                self.total_burned += br
                self.accounts[BURN_ADDR] = self.accounts.get(BURN_ADDR, 0) + br
                self.total_supply += rw
                self.total_dev_reward += dr
                self.total_burn_reward += br
                self.total_relay_reward += rr
                block_dev = dr
                block_burn = br
                block_relay = rr

            self.total_supply += block_fees

            blk = {
                "height": self.height, "previous_hash": self.last_hash,
                "transactions": txs, "timestamp": int(now),
                "reward": rw, "total_fees": block_fees,
                "total_supply": self.total_supply, "version": PROTOCOL
            }
            blk["hash"] = hashlib.sha256(json.dumps(blk, sort_keys=True).encode()).hexdigest()
            self.chain.append(blk)
            self.last_hash = blk["hash"]
            self.height += 1
            self.last_block_time = now

            sigs = {tx.get("signature") for tx in txs}
            self.mempool_sigs -= sigs
            self.mempool = deque([tx for tx in self.mempool if tx.get("signature") not in sigs], maxlen=10000)

            if self.height % RELAY_DISTRIBUTION_INTERVAL == 0 and self.total_relay > 0:
                self.distribute_relay_pool()

            self._save()
            asyncio.create_task(self._notify(blk))

            total_dev = block_dev + block_fee_dev
            total_relay_block = block_relay + block_fee_relay
            total_burn = block_burn + block_fee_burn

            log.info(f"")
            log.info(f"{C_BOLD}{C_GREEN}  BLOCK #{blk['height']}{C_RESET}  {'─' * 35}")
            log.info(f"  {C_WHITE}Transactions: {len(txs)}{C_RESET}  |  "
                     f"{C_WHITE}Reward: {C_BOLD}{rw / COIN:.2f} RAM{C_RESET}  |  "
                     f"{C_WHITE}Fees: {block_fees / COIN:.4f} RAM{C_RESET}")
            log.info(f"  {'─' * 49}")
            log.info(f"  {C_MAGENTA}Dev:     {C_BOLD}{total_dev / COIN:.4f} RAM{C_RESET}  "
                     f"({C_DIM}reward {block_dev / COIN:.2f} + fees {block_fee_dev / COIN:.4f}{C_RESET})")
            log.info(f"  {C_BLUE}Relay:   {C_BOLD}{total_relay_block / COIN:.4f} RAM{C_RESET}  "
                     f"({C_DIM}reward {block_relay / COIN:.2f} + fees {block_fee_relay / COIN:.4f}{C_RESET})")
            log.info(f"  {C_RED}Burned:  {C_BOLD}{total_burn / COIN:.4f} RAM{C_RESET}  "
                     f"({C_DIM}reward {block_burn / COIN:.2f} + fees {block_fee_burn / COIN:.4f}{C_RESET})")
            log.info(f"  {'─' * 49}")
            log.info(f"  {C_GREEN}Supply:     {C_BOLD}{self.fmt(self.total_supply / COIN)} RAM{C_RESET}")
            log.info(f"  {C_RED}Burned:     {C_BOLD}{self.fmt(self.total_burned / COIN)} RAM{C_RESET}")
            log.info(f"  {C_BLUE}Relay pool: {C_BOLD}{self.fmt(self.total_relay)} RAM{C_RESET}  "
                     f"({C_DIM}undistributed{C_RESET})")
            log.info(f"  {C_YELLOW}Dev total:  {C_BOLD}{self.fmt(self.total_dev_reward / COIN)} RAM{C_RESET}")
            log.info(f"  {C_GREEN}{'─' * 49}{C_RESET}")
            log.info(f"")

            return blk

    def _save(self):
        try:
            with sqlite3.connect(DB_V11) as conn:
                conn.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, val TEXT)')
                for k, v in [
                    ('height', str(self.height)), ('accounts', json.dumps(self.accounts)),
                    ('nonces', json.dumps(self.nonces)), ('total_supply', str(self.total_supply)),
                    ('total_burned', str(self.total_burned)), ('total_tx', str(self.total_tx)),
                    ('last_hash', self.last_hash),
                    ('total_dev_reward', str(self.total_dev_reward)),
                    ('total_relay_reward', str(self.total_relay_reward)),
                    ('total_burn_reward', str(self.total_burn_reward)),
                    ('total_relay_distributed', str(self.total_relay_distributed))
                ]:
                    conn.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (k, v))
                conn.commit()
        except:
            pass

    async def _notify(self, blk):
        msg = json.dumps({"event": "new_block", "height": self.height, "hash": blk["hash"]})
        dead = set()
        for ws in self.ws_clients:
            if not ws.closed:
                try:
                    await ws.send_str(msg)
                except:
                    dead.add(ws)
        self.ws_clients -= dead

    def get_addr(self, addr):
        if not addr.startswith("RAM_"): return None
        return {
            "address": addr,
            "balance": self.accounts.get(addr, 0) / COIN,
            "relay_balance": self.relay_balances.get(addr, 0.0),
            "nonce": self.nonces.get(addr, 0)
        }

    def stats(self):
        return {
            "version": VERSION, "protocol": "PARASITE", "height": self.height,
            "accounts": len(self.accounts), "mempool": len(self.mempool), "total_tx": self.total_tx,
            "total_supply": self.total_supply / COIN, "total_burned": self.total_burned / COIN,
            "relay_pool": self.total_relay, "relay_distributed": self.total_relay_distributed,
            "relay_nodes": len(self.relay_balances),
            "total_dev_reward": self.total_dev_reward / COIN,
            "total_burn_reward": self.total_burn_reward / COIN,
            "total_relay_reward": self.total_relay_reward / COIN,
            "total_fees_collected": self.total_fees_collected / COIN,
            "current_reward": self.reward_at(self.height) / COIN,
            "next_halving": HALVING - (self.height % HALVING),
            "block_time": BLOCK_TIME, "uptime": int(time.time() - self.start_time)
        }


class API:
    def __init__(self, bc, pm, node_peer_id):
        self.bc = bc
        self.pm = pm
        self.node_peer_id = node_peer_id

    async def health(self, req):
        return web.json_response({"ok": True, "version": VERSION, "height": self.bc.height, "peers": self.pm.count()})

    async def stats(self, req):
        return web.json_response(self.bc.stats())

    async def addr(self, req):
        d = self.bc.get_addr(req.match_info['addr'])
        return web.json_response(d) if d else web.json_response({"error": "not found"}, status=404)

    async def tx(self, req):
        try:
            tx = await req.json()
        except:
            return web.json_response({"status": "error", "reason": "invalid json"}, status=400)
        ok, why = await self.bc.add_tx(tx)
        return web.json_response({"status": "ok" if ok else "rejected", "reason": why})

    async def pending(self, req):
        return web.json_response(list(self.bc.mempool))

    async def chain(self, req):
        lim = min(int(req.query.get("limit", 100)), 5000)
        self.bc.record_relay(self.node_peer_id, 1000)
        return web.json_response(self.bc.chain[-lim:])

    async def peers(self, req):
        return web.json_response({
            "peers": [{"address": a, "height": p["height"]} for a, p in self.pm.get_active(50)],
            "count": self.pm.count()
        })

    async def top(self, req):
        lim = min(int(req.query.get("limit", 10)), 100)
        t = sorted(self.bc.accounts.items(), key=lambda x: x[1], reverse=True)[:lim]
        return web.json_response([{"address": a, "balance": b / COIN, "relay_balance": self.bc.relay_balances.get(a, 0)}
                                  for a, b in t])

    async def ws(self, req):
        ws = web.WebSocketResponse(heartbeat=30, timeout=60)
        await ws.prepare(req)
        self.bc.ws_clients.add(ws)
        try:
            await ws.send_json({"event": "connected", "height": self.bc.height})
            async for m in ws:
                if m.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    break
        except:
            pass
        finally:
            self.bc.ws_clients.discard(ws)
        return ws


class Node:
    def __init__(self):
        self.bc = Blockchain()
        self.pm = PeerManager()
        self.github = GitHubClient()
        self.node_peer_id = f"127.0.0.1:{API_PORT}"
        self.api = API(self.bc, self.pm, self.node_peer_id)
        self.running = False

    async def start(self):
        self.running = True

        addr = get_address()
        log.info(f"{C_GREEN}Node wallet: {addr[:30]}...{C_RESET}")
        self.bc.relay_addresses[self.node_peer_id] = addr

        mode = f"{C_GREEN}SEED{C_RESET}" if HAS_TOKEN else f"{C_CYAN}CLIENT{C_RESET}"
        db_status = f"{C_GREEN}v10 DB found{C_RESET}" if HAS_V10 else f"{C_YELLOW}Fresh start{C_RESET}"

        log.info(f"{C_BOLD}{C_CYAN}{'=' * 55}{C_RESET}")
        log.info(f"{C_BOLD}  RAMCOIN v{VERSION} - PARASITE PROTOCOL{C_RESET}")
        log.info(f"{C_BOLD}{C_CYAN}{'=' * 55}{C_RESET}")
        log.info(f"  Mode: {mode}")
        log.info(f"  Status: {db_status}")
        log.info(f"  Wallet: {addr[:30]}...")
        log.info(f"  Block: {BLOCK_TIME}s | Halving: {HALVING:,} blocks")
        log.info(f"  Reward: {INITIAL_REWARD / COIN} RAM | Max: ~17.5M")
        log.info(f"  Split: Dev {DEV_SHARE}% | Relay {RELAY_SHARE}% | Burn {BURN_SHARE}%")
        log.info(f"  Fee: {FIXED_FEE / COIN} RAM | Relay interval: {RELAY_DISTRIBUTION_INTERVAL} blocks")
        log.info(f"  Gist update: {GIST_UPDATE_INTERVAL}s | Gossip: {GOSSIP_INTERVAL}s")

        await self.github.start()
        await self.bc.init(self.github)

        if HAS_TOKEN and not self.github.gist_id:
            gid = await self.github.create_gist(GIST_PEERS,
                                                json.dumps(
                                                    {"peers": [], "height": self.bc.height, "timestamp": int(time.time())}))
            if gid:
                self.github.gist_id = gid
                log.info(f"  {C_GREEN}Gist: {gid}{C_RESET}")

        app = web.Application(client_max_size=10 * 1024 * 1024)

        @web.middleware
        async def cors(req, handler):
            resp = await handler(req)
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Server'] = 'RAMCOIN'
            return resp

        app.middlewares.append(cors)
        app.router.add_get('/health', self.api.health)
        app.router.add_get('/stats', self.api.stats)
        app.router.add_get('/chain', self.api.chain)
        app.router.add_get('/address/{addr}', self.api.addr)
        app.router.add_post('/tx', self.api.tx)
        app.router.add_get('/pending', self.api.pending)
        app.router.add_get('/peers', self.api.peers)
        app.router.add_get('/top', self.api.top)
        app.router.add_get('/ws', self.api.ws)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", API_PORT)
        await site.start()

        log.info(f"  {C_GREEN}API: http://127.0.0.1:{API_PORT}{C_RESET}")

        asyncio.create_task(self._blocks())
        asyncio.create_task(self._gist_sync())
        asyncio.create_task(self._peer_sync())
        asyncio.create_task(self._gossip())

        log.info(f"{C_BOLD}{C_GREEN}{'=' * 55}{C_RESET}")
        log.info(
            f"{C_BOLD}{C_GREEN}  NODE READY | Height: {self.bc.height} | Supply: {self.bc.fmt(self.bc.total_supply / COIN)} RAM{C_RESET}")
        log.info(f"{C_BOLD}{C_GREEN}{'=' * 55}{C_RESET}")
        log.info(f"")

        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def _blocks(self):
        while self.running:
            await asyncio.sleep(2)
            try:
                await self.bc.make_block()
            except Exception as e:
                log.error(f"Block error: {e}")

    async def _gist_sync(self):
        while self.running:
            await asyncio.sleep(GIST_UPDATE_INTERVAL)
            if HAS_TOKEN and self.github.gist_id:
                try:
                    peers = [{"address": a, "height": p["height"]} for a, p in self.pm.get_active(20)]
                    await self.github.update_gist(GIST_PEERS,
                                                  json.dumps(
                                                      {"peers": peers, "height": self.bc.height, "timestamp": int(time.time())}))
                    await self.github.update_gist(GIST_STATE,
                                                  json.dumps({"height": self.bc.height, "last_hash": self.bc.last_hash,
                                                              "total_supply": self.bc.total_supply, "timestamp": int(time.time())}))
                except:
                    pass

    async def _peer_sync(self):
        while self.running:
            await asyncio.sleep(GIST_SEARCH_INTERVAL)
            try:
                gists = await self.github.find_peers()
                if self.github.gist_id:
                    gists.append(self.github.gist_id)
                for gid in gists[:5]:
                    d = await self.github.read_gist(gid, GIST_PEERS)
                    if d:
                        try:
                            info = json.loads(d)
                            for p in info.get("peers", []):
                                addr = p.get("address", "")
                                if addr:
                                    await self.pm.add(addr, p.get("height", 0))
                        except:
                            pass
            except:
                pass

    async def _gossip(self):
        while self.running:
            await asyncio.sleep(GOSSIP_INTERVAL)
            active = self.pm.get_active(10)
            for paddr, info in active:
                if paddr == self.node_peer_id:
                    continue
                try:
                    data = await self.github._get(f"http://{paddr}/peers")
                    if data and isinstance(data, dict):
                        for p in data.get("peers", []):
                            new_addr = p.get("address", "")
                            if new_addr:
                                await self.pm.add(new_addr, p.get("height", 0))
                except:
                    pass

    async def stop(self):
        self.running = False
        await self.github.stop()
        log.info(f"{C_YELLOW}Node stopped{C_RESET}")


async def main():
    node = Node()
    await node.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bye")
    except Exception as e:
        log.critical(f"FATAL: {e}")
        import traceback
        traceback.print_exc()
