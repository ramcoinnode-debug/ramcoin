#!/usr/bin/env python3
"""
RAMCOIN MINER v7.0.3 — SOLO + POOL
Исправлено: добавлен pool_block=False для соло-блоков.
"""

import hashlib, json, os, secrets, sys, threading, time, array, signal, traceback, ctypes, ctypes.util, platform, re
from datetime import datetime
from collections import deque

try:
    import websocket
except ImportError:
    print("pip install websocket-client");
    sys.exit(1)

try:
    import psutil;

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from hashlib import pbkdf2_hmac
from Crypto.Cipher import AES
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

VERSION = "7.0.3"
COIN = 100_000_000
MAX_TARGET = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
SCRATCHPAD_ITER = 4096
BASE_BUFFER_SIZE = 524288
MAX_BUFFER_SIZE = 4194304
MAX_HOME_CORES = 16
MAX_HOME_L3_MB = 64
MAX_HOME_THREADS = 8
MAX_SERVER_THREADS = 8
SERVER_PENALTY = 0.25

NODES = [{"http": "http://localhost:5000", "ws": "ws://localhost:5000/ws"}]
NODE_TIMEOUT = 15
SUBMIT_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2
WS_RECONNECT_DELAY = 3
HEARTBEAT_INTERVAL = 15
BLOCK_TIMEOUT = 300
SPEED_SMOOTHING = 0.85
SPEED_UPDATE_INTERVAL = 0.3
LOG_INTERVAL = 10


class HardwareDetector:
    def __init__(self):
        self.is_server = False;
        self.server_reasons = []
        self.total_cores = os.cpu_count() or 2
        self.physical_cores = self._get_physical_cores()
        self.l3_cache_mb = 0;
        self.cpu_model = "";
        self.cpu_vendor = ""
        self.recommended_threads = 2;
        self.scratchpad_size = BASE_BUFFER_SIZE;
        self.server_penalty = 1.0
        self._detect()

    def _get_physical_cores(self):
        try:
            if platform.system() == "Linux":
                with open('/proc/cpuinfo') as f:
                    content = f.read()
                phys_ids = set(re.findall(r'physical id\s*:\s*(\d+)', content))
                if phys_ids:
                    cores_per_socket = set(re.findall(r'cpu cores\s*:\s*(\d+)', content))
                    if cores_per_socket: return len(phys_ids) * int(cores_per_socket.pop())
            if HAS_PSUTIL: return psutil.cpu_count(logical=False)
        except:
            pass
        return max(1, self.total_cores // 2)

    def _detect(self):
        try:
            with open('/proc/cpuinfo') as f:
                for line in f:
                    if 'model name' in line: self.cpu_model = line.split(':')[1].strip(); break
        except:
            self.cpu_model = platform.processor() or "Unknown"
        cpu_lower = self.cpu_model.lower()
        if any(k in cpu_lower for k in ['amd', 'ryzen', 'athlon', 'epyc']):
            self.cpu_vendor = "amd"
        elif any(k in cpu_lower for k in ['intel', 'xeon', 'core', 'pentium', 'celeron']):
            self.cpu_vendor = "intel"
        elif any(k in cpu_lower for k in ['apple', 'm1', 'm2', 'm3', 'm4']):
            self.cpu_vendor = "apple"
        else:
            self.cpu_vendor = "unknown"
        self.l3_cache_mb = self._get_l3_cache();
        self._check_server();
        self._configure()

    def _get_l3_cache(self):
        try:
            if platform.system() == "Linux":
                l3 = 0
                for cpu_dir in os.listdir('/sys/devices/system/cpu'):
                    if cpu_dir.startswith('cpu') and cpu_dir[3:].isdigit():
                        cache_path = f'/sys/devices/system/cpu/{cpu_dir}/cache'
                        if os.path.exists(cache_path):
                            for idx in os.listdir(cache_path):
                                level_path = f'{cache_path}/{idx}/level';
                                size_path = f'{cache_path}/{idx}/size'
                                if os.path.exists(level_path):
                                    with open(level_path) as f:
                                        if f.read().strip() == '3':
                                            if os.path.exists(size_path):
                                                with open(size_path) as f: l3 = max(l3,
                                                                                    self._parse_size(f.read().strip()))
                if l3 > 0: return l3
        except:
            pass
        cpu_l = self.cpu_model.lower()
        if 'ryzen 9 79' in cpu_l or 'ryzen 9 59' in cpu_l:
            return 64
        elif 'ryzen 9' in cpu_l:
            return 32
        elif 'ryzen 7 78' in cpu_l or 'ryzen 7 58' in cpu_l:
            return 32
        elif 'ryzen 7' in cpu_l:
            return 16
        elif 'ryzen 5 56' in cpu_l or 'ryzen 5 76' in cpu_l:
            return 32
        elif 'ryzen 5' in cpu_l:
            return 16
        elif 'ryzen 3' in cpu_l:
            return 8
        elif 'i9-' in cpu_l:
            return 30
        elif 'i7-' in cpu_l:
            return 24
        elif 'i5-' in cpu_l:
            return 18
        elif 'i3-' in cpu_l:
            return 12
        return 8

    def _parse_size(self, size_str):
        size_str = size_str.strip().upper()
        if size_str.endswith('K'):
            return int(size_str[:-1]) // 1024
        elif size_str.endswith('M'):
            return int(size_str[:-1])
        elif size_str.endswith('G'):
            return int(size_str[:-1]) * 1024
        else:
            try:
                return int(size_str) // (1024 * 1024)
            except:
                return 0

    def _check_server(self):
        cpu_lower = self.cpu_model.lower()
        server_kw = ['xeon', 'epyc', 'opteron', 'platinum', 'gold ', 'silver ', 'threadripper pro']
        detected = False
        for kw in server_kw:
            if kw in cpu_lower: detected = True; self.server_reasons.append(f"Server CPU: {kw.upper()}"); break
        if 'threadripper' in cpu_lower and 'pro' in cpu_lower: detected = True
        if 'threadripper' in cpu_lower and 'pro' not in cpu_lower: detected = True
        if self.physical_cores > MAX_HOME_CORES: detected = True
        if self.l3_cache_mb > MAX_HOME_L3_MB: detected = True
        home_whitelist = ['ryzen 9 7950x', 'ryzen 9 5950x', 'ryzen 9 3950x', 'i9-14900k', 'i9-13900k', 'i9-12900k',
                          'ryzen 7 7800x3d', 'ryzen 7 5800x3d', 'core ultra 9']
        if detected:
            for hw in home_whitelist:
                if hw in cpu_lower and self.physical_cores <= 16: detected = False; break
        self.is_server = detected

    def _configure(self):
        if self.is_server:
            self.recommended_threads = MAX_SERVER_THREADS; self.server_penalty = SERVER_PENALTY; self.scratchpad_size = BASE_BUFFER_SIZE * 2
        else:
            optimal = max(2, min(MAX_HOME_THREADS, self.l3_cache_mb // 4))
            optimal = min(optimal, self.physical_cores);
            optimal = min(optimal, self.total_cores)
            self.recommended_threads = optimal;
            self.server_penalty = 1.0;
            self.scratchpad_size = BASE_BUFFER_SIZE

    def get_effective_threads(self):
        return self.recommended_threads

    def get_thread_memory_mb(self):
        return self.scratchpad_size * 8 / (1024 * 1024)


hw = HardwareDetector()


class MinerState:
    def __init__(self):
        self.lock = threading.RLock()
        self.height = -1;
        self.prev_hash = "";
        self.target = 0;
        self.reward = 10.0
        self.txs = [];
        self.active = False;
        self.block_found = False
        self.node_ok = False;
        self.ws_ok = False;
        self.primary_node = 0
        self.mined = 0;
        self.total_ram = 0.0;
        self.rejected = 0
        self.start_time = time.time();
        self.speed = 0.0
        self.thread_speeds = {};
        self.thread_updates = {}
        self.template_version = 0;
        self.template_lock = threading.RLock()
        self.submitted_blocks = set()
        self.current_buffer_size = hw.scratchpad_size
        self.pool_mode = False;
        self.pool_shares = 0

    def update_speed(self, tid, sols):
        with self.lock:
            now = time.time();
            last = self.thread_updates.get(tid, now - 1)
            elapsed = max(0.01, now - last);
            instant = sols / elapsed
            self.speed = instant if self.speed == 0 else self.speed * SPEED_SMOOTHING + instant * (1 - SPEED_SMOOTHING)
            self.thread_speeds[tid] = instant;
            self.thread_updates[tid] = now

    def get_template(self):
        with self.template_lock:
            return (self.height, self.prev_hash, self.target, self.reward, self.txs, self.template_version,
                    self.current_buffer_size)

    def get_node_url(self): return NODES[self.primary_node]["http"]

    def get_ws_url(self): return NODES[self.primary_node]["ws"]

    def switch_node(self):
        with self.lock: self.primary_node = (self.primary_node + 1) % len(NODES)


state = MinerState()


def fmt_speed(v):
    if v >= 1e9: return f"{v / 1e9:.2f} GRam/s"
    if v >= 1e6: return f"{v / 1e6:.2f} MRam/s"
    if v >= 1e3: return f"{v / 1e3:.2f} KRam/s"
    return f"{v:.2f} Ram/s"


def fmt_time(s):
    if s < 0: return "00:00:00"
    h, m = int(s) // 3600, (int(s) % 3600) // 60
    return f"{h:02d}:{m:02d}:{int(s) % 60:02d}"


def safe_request(url, data=None, timeout=NODE_TIMEOUT, max_retries=MAX_RETRIES):
    import urllib.request, urllib.error
    for attempt in range(max_retries):
        try:
            if data is None:
                req = urllib.request.Request(url, headers={"Connection": "close"})
            else:
                req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                             headers={"Content-Type": "application/json", "Connection": "close"},
                                             method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                state.node_ok = True; return json.loads(r.read().decode())
        except:
            time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
    state.node_ok = False;
    return None


def sign_block(block, priv_hex):
    try:
        priv = ec.derive_private_key(int(priv_hex, 16), ec.SECP256K1())
        data = {"index": block["index"], "previous_hash": block["previous_hash"], "timestamp": block["timestamp"],
                "nonce": block["nonce"], "nonce_seed": block.get("nonce_seed", 0),
                "memory_proof": block["memory_proof"],
                "miner_payout_address": block["miner_payout_address"],
                "scratchpad_mods": block.get("scratchpad_mods", 0)}
        return priv.sign(json.dumps(data, sort_keys=True).encode(), ec.ECDSA(hashes.SHA256())).hex()
    except:
        return None


def create_scratchpad(prev_hash, tid, nseed, buffer_size=None):
    size = buffer_size or state.current_buffer_size
    sp = array.array('Q', [0]) * size
    seed = int(hashlib.sha256(f"{prev_hash}|{tid}|{nseed}|RAMCOIN_v7|{size}".encode()).hexdigest(), 16)
    s0, s1 = seed, seed ^ 0xDEADBEEF
    for i in range(size):
        s1, s0 = s0 & 0xFFFFFFFFFFFFFFFF, s1
        s1 ^= (s1 << 23) & 0xFFFFFFFFFFFFFFFF;
        s1 ^= (s1 >> 17);
        s1 ^= s0;
        s1 ^= (s0 >> 26)
        sp[i] = (s0 + s1) & 0xFFFFFFFFFFFFFFFF
    return sp, seed, size


def memhard_loop(sp, seed, nonce, nseed, buffer_size=None):
    size = buffer_size or state.current_buffer_size
    mix = seed;
    mods = 0
    for k in range(SCRATCHPAD_ITER):
        if k & 63 == 0:
            if not state.active or state.block_found: return None, None, None
        mix = (mix * 0x9E3779B97F4A7C15 + nonce + nseed) & 0xFFFFFFFFFFFFFFFF
        mix ^= (mix >> 33);
        mix ^= (mix << 13)
        idx = mix % size;
        rv = sp[idx]
        sp[idx] = (rv ^ mix ^ nonce) & 0xFFFFFFFFFFFFFFFF;
        mods += 1
        mix = (mix + rv) & 0xFFFFFFFFFFFFFFFF
        if k % 256 == 0:
            idx2 = ((idx * 1103515245 + 12345) ^ rv) % size
            sp[idx2] = (sp[idx2] ^ (mix >> 16) ^ nonce) & 0xFFFFFFFFFFFFFFFF;
            mods += 1
        if k > 0 and k % 50000 == 0: nseed = (nseed + 1) & 0xFFFFFFFF; mix = (mix ^ nseed) & 0xFFFFFFFFFFFFFFFF
    return mix, nseed, mods


def verify_solution(prev_hash, nonce, nseed, mix, mods, target):
    try:
        proof = hashlib.sha256(f"{mix}{prev_hash}{nseed}{mods}".encode()).hexdigest()
        return int(proof, 16) <= target, proof
    except:
        return False, ""


class MinerThread:
    """Соло-майнер"""

    def __init__(self, tid, address, priv_key):
        self.tid = tid;
        self.address = address;
        self.priv_key = priv_key
        self.nonce = secrets.randbits(32);
        self.nseed = secrets.randbits(16)
        self.iterations = 0;
        self.last_restart = time.time();
        self.thread = None
        self.skip_counter = 0
        self.skip_rate = int(1.0 / hw.server_penalty) if hw.is_server and hw.server_penalty > 0 else 0

    def run(self):
        if HAS_PSUTIL:
            try:
                p = psutil.Process();
                cpu_count = psutil.cpu_count(logical=True)
                phys = psutil.cpu_count(logical=False)
                os.sched_setaffinity(0, {self.tid % phys if phys else self.tid % cpu_count})
            except:
                pass
        self.last_restart = time.time()
        while state.active:
            try:
                self._mine_loop()
            except Exception as e:
                time.sleep(1)
            self.nonce = secrets.randbits(32);
            self.nseed = secrets.randbits(16)

    def _mine_loop(self):
        height, prev_hash, target, reward, txs, tpl_ver, buf_size = state.get_template()
        try:
            sp, seed, actual_size = create_scratchpad(prev_hash, self.tid, self.nseed, buf_size)
        except:
            time.sleep(0.5); return

        local_sol = 0;
        last_report = time.time()
        while state.active and not state.block_found:
            if hw.is_server and self.skip_rate > 1:
                self.skip_counter += 1
                if self.skip_counter % self.skip_rate != 0: self.nonce = (self.nonce + 1) & 0xFFFFFFFF; continue

            cur = state.get_template()
            if cur[5] != tpl_ver:
                height, prev_hash, target, reward, txs, tpl_ver, buf_size = cur
                try:
                    sp, seed, actual_size = create_scratchpad(prev_hash, self.tid, self.nseed, buf_size)
                except:
                    return
                self.nonce = secrets.randbits(32);
                self.nseed = secrets.randbits(16);
                self.iterations = 0

            if time.time() - self.last_restart > BLOCK_TIMEOUT:
                self.nonce = secrets.randbits(32);
                self.nseed = secrets.randbits(16);
                self.last_restart = time.time()
                try:
                    sp, seed, actual_size = create_scratchpad(prev_hash, self.tid, self.nseed, buf_size)
                except:
                    return

            try:
                sp_copy = array.array('Q', sp)
                mix, new_nseed, mods = memhard_loop(sp_copy, seed, self.nonce, self.nseed, actual_size)
                if mix is None: return

                local_sol += 1;
                self.iterations += 1
                now = time.time()
                if now - last_report >= SPEED_UPDATE_INTERVAL: state.update_speed(self.tid,
                                                                                  local_sol); local_sol = 0; last_report = now

                is_valid, proof = verify_solution(prev_hash, self.nonce, self.nseed, mix, mods, target)
                if is_valid:
                    is_valid2, _ = verify_solution(prev_hash, self.nonce, self.nseed, mix, mods, target)
                    if not is_valid2: self.nonce = (self.nonce + 1) & 0xFFFFFFFF; continue

                    with state.lock:
                        if state.block_found or state.height != height: return
                        state.block_found = True

                    # ===== ИСПРАВЛЕНО: добавлен pool_block: False =====
                    block = {"index": height, "previous_hash": prev_hash, "transactions": txs,
                             "timestamp": int(time.time()),
                             "nonce": int(self.nonce), "nonce_seed": int(self.nseed), "memory_proof": proof,
                             "target": target,
                             "extra_nonce": self.tid, "miner_payout_address": self.address, "scratchpad_mods": mods,
                             "scratchpad_size": actual_size, "pool_block": False}

                    sig = sign_block(block, self.priv_key)
                    if not sig: state.block_found = False; self.nonce = secrets.randbits(32); continue
                    block["miner_signature"] = sig

                    block_hash = hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()
                    with state.lock:
                        if block_hash in state.submitted_blocks: state.block_found = False; return
                        state.submitted_blocks.add(block_hash)

                    chain_check = safe_request(f"{state.get_node_url()}/chain", timeout=5)
                    if not chain_check or chain_check.get("length", -1) != height:
                        state.block_found = False;
                        state.rejected += 1;
                        return

                    resp = safe_request(f"{state.get_node_url()}/mine", block, timeout=SUBMIT_TIMEOUT, max_retries=3)
                    if resp and resp.get("status") == "ok":
                        state.mined += 1;
                        state.total_ram += reward
                        print(
                            f"[{fmt_time(time.time() - state.start_time)}] BLOCK #{height} ACCEPTED +{reward:.2f} RAM")
                    else:
                        state.rejected += 1;
                        state.block_found = False
                        reason = resp.get("reason", "unknown") if resp else "no response"
                        print(f"[{fmt_time(time.time() - state.start_time)}] BLOCK #{height} REJECTED: {reason}")
                    return

                self.nonce = (self.nonce + 1) & 0xFFFFFFFF
                if self.nonce > 2 ** 48: self.nonce = secrets.randbits(32); self.nseed = secrets.randbits(
                    16); self.iterations = 0
            except:
                self.nonce = secrets.randbits(32); time.sleep(0.1)


class PoolThread:
    """Пул-майнер"""

    def __init__(self, tid, address):
        self.tid = tid;
        self.address = address
        self.nonce = secrets.randbits(32);
        self.nseed = secrets.randbits(16)
        self.last_restart = time.time();
        self.thread = None

    def run(self):
        if HAS_PSUTIL:
            try:
                p = psutil.Process();
                cpu_count = psutil.cpu_count(logical=True)
                phys = psutil.cpu_count(logical=False)
                os.sched_setaffinity(0, {self.tid % phys if phys else self.tid % cpu_count})
            except:
                pass
        while state.active:
            try:
                self._pool_loop()
            except:
                time.sleep(1)
            self.nonce = secrets.randbits(32);
            self.nseed = secrets.randbits(16)

    def _pool_loop(self):
        while state.active and not state.block_found:
            tmpl = safe_request(f"{state.get_node_url()}/pool/template", timeout=5)
            if not tmpl: time.sleep(2); continue
            prev_hash = tmpl["previous_hash"];
            pool_target = tmpl.get("pool_target", state.target * 100)
            buf_size = state.current_buffer_size
            try:
                sp, seed, actual_size = create_scratchpad(prev_hash, self.tid, self.nseed, buf_size)
            except:
                time.sleep(0.5); continue
            local_sol = 0;
            last_report = time.time()
            while state.active and not state.block_found:
                if time.time() - self.last_restart > 60: self.last_restart = time.time(); break
                try:
                    sp_copy = array.array('Q', sp)
                    mix, new_nseed, mods = memhard_loop(sp_copy, seed, self.nonce, self.nseed, actual_size)
                    if mix is None: return
                    local_sol += 1
                    now = time.time()
                    if now - last_report >= SPEED_UPDATE_INTERVAL: state.update_speed(self.tid,
                                                                                      local_sol); local_sol = 0; last_report = now
                    is_share, _ = verify_solution(prev_hash, self.nonce, self.nseed, mix, mods, pool_target)
                    if is_share:
                        share_data = {"miner_address": self.address, "nonce": int(self.nonce),
                                      "nonce_seed": int(self.nseed),
                                      "mix": str(mix), "mods": mods, "extra_nonce": self.tid}
                        resp = safe_request(f"{state.get_node_url()}/pool/share", share_data, timeout=5)
                        if resp and resp.get("status") == "ok": state.pool_shares += 1
                    self.nonce = (self.nonce + 1) & 0xFFFFFFFF
                    if self.nonce > 2 ** 48: self.nonce = secrets.randbits(32); self.nseed = secrets.randbits(16)
                except:
                    self.nonce = secrets.randbits(32); time.sleep(0.1)


def logger(threads, address):
    last_log = 0
    while True:
        time.sleep(1)
        now = time.time()
        if now - last_log >= LOG_INTERVAL:
            s = state;
            mode = "POOL" if s.pool_mode else "SOLO"
            print(
                f"[{fmt_time(time.time() - s.start_time)}] {mode} | {fmt_speed(s.speed)} | Blocks: {s.mined} | Rejected: {s.rejected} | Height: #{s.height} | Reward: {s.reward:.2f} RAM",
                flush=True)
            last_log = now


def ws_client():
    while True:
        try:
            ws = websocket.create_connection(state.get_ws_url(), timeout=10, ping_interval=HEARTBEAT_INTERVAL,
                                             ping_timeout=5)
            state.ws_ok = True;
            state.node_ok = True
            ws.send(json.dumps({"type": "miner", "version": VERSION,
                                "hardware": {"cpu": hw.cpu_model, "vendor": hw.cpu_vendor,
                                             "cores_physical": hw.physical_cores, "cores_logical": hw.total_cores,
                                             "l3_mb": hw.l3_cache_mb, "is_server": hw.is_server}}))
            while True:
                try:
                    data = json.loads(ws.recv())
                    if data.get("event") == "new_block":
                        state.block_found = True
                        chain = safe_request(f"{state.get_node_url()}/chain")
                        if chain:
                            with state.template_lock: state.height = chain["length"]; state.prev_hash = \
                            chain["chain"][-1]["hash"]; state.target = chain.get("current_target",
                                                                                 0); state.reward = 10.0 / (
                                        2 ** (state.height // 876000)); state.txs = safe_request(
                                f"{state.get_node_url()}/pending") or []; state.template_version += 1
                except websocket.WebSocketTimeoutException:
                    continue
                except:
                    break
        except:
            state.ws_ok = False; time.sleep(WS_RECONNECT_DELAY)


def load_wallet():
    for wf in ["ramcoin_wallet.json", "wallet.json", os.path.expanduser("~/.ramcoin/wallet.json")]:
        if not os.path.exists(wf): continue
        try:
            with open(wf) as f:
                data = json.load(f)
            if "private_key_hex" in data and len(data["private_key_hex"]) == 64 and data.get("address", "").startswith(
                "RAM_"): return data["private_key_hex"], data["address"]
            if "crypto_data" in data:
                for i in range(3):
                    pw = input(f"Password ({i + 1}/3): ").strip()
                    if not pw: continue
                    try:
                        raw = bytes.fromhex(data["crypto_data"]);
                        key = pbkdf2_hmac('sha512', pw.encode(), raw[:32], 600000, dklen=32)
                        cipher = AES.new(key, AES.MODE_GCM, nonce=raw[32:48])
                        dec = json.loads(cipher.decrypt_and_verify(raw[64:], raw[48:64]))
                        if len(dec["private_key_hex"]) == 64 and dec["address"].startswith("RAM_"): return dec[
                            "private_key_hex"], dec["address"]
                    except:
                        pass
        except:
            pass
    return None, None


def main():
    print(f"RAMCOIN MINER v{VERSION}")
    print(f"CPU: {hw.cpu_model[:55]}")
    print(f"{hw.cpu_vendor.upper()} | {hw.physical_cores}P/{hw.total_cores}L | L3: {hw.l3_cache_mb}MB")
    if hw.is_server:
        print(f"SERVER — Penalty: {int((1 - hw.server_penalty) * 100)}%")
    else:
        print(f"HOME PC — Full hashrate")
    threads = hw.get_effective_threads()
    print(f"Threads: {threads} | {hw.get_thread_memory_mb():.0f}MB/thread")

    print(f"\nSelect mode: 1. SOLO  2. POOL")
    while True:
        c = input(f"Choose [1/2]: ").strip()
        if c in ("1", "2"): break
    state.pool_mode = (c == "2")
    mode_str = "POOL" if state.pool_mode else "SOLO"
    print(f"Mode: {mode_str}")

    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True);
        libc.mlockall(1 | 2)
    except:
        pass

    def sig_handler(sig, frame):
        print(
            f"\nBlocks: {state.mined} | RAM: {state.total_ram:.4f} | Rejected: {state.rejected} | Shares: {state.pool_shares}")
        state.active = False;
        state.block_found = True;
        time.sleep(0.5);
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)

    priv_hex, address = load_wallet()
    if not priv_hex: print("Wallet not found\n"); sys.exit(1)
    print(f"Address: {address[:42]}...\n")

    threading.Thread(target=logger, args=(threads, address), daemon=True).start()
    threading.Thread(target=ws_client, daemon=True).start()

    print("Connecting...")
    chain = None
    for _ in range(30):
        chain = safe_request(f"{state.get_node_url()}/chain")
        if chain: break
        time.sleep(1)
    if not chain: print("Cannot connect\n"); sys.exit(1)

    with state.template_lock:
        state.height = chain["length"];
        state.prev_hash = chain["chain"][-1]["hash"]
        state.target = chain.get("current_target", 0);
        state.reward = 10.0 / (2 ** (state.height // 876000))
        state.txs = safe_request(f"{state.get_node_url()}/pending") or [];
        state.template_version = 1

    state.active = True
    print(
        f"Height: #{state.height} | Diff: {fmt_speed(MAX_TARGET / max(1, state.target))} | Reward: {state.reward} RAM\n")

    miner_threads = []
    if state.pool_mode:
        for tid in range(threads):
            pt = PoolThread(tid, address);
            t = threading.Thread(target=pt.run, daemon=True, name=f"p-{tid}")
            t.start();
            pt.thread = t;
            miner_threads.append(pt)
    else:
        for tid in range(threads):
            mt = MinerThread(tid, address, priv_hex);
            t = threading.Thread(target=mt.run, daemon=True, name=f"m-{tid}")
            t.start();
            mt.thread = t;
            miner_threads.append(mt)

    while True:
        time.sleep(1)
        if state.block_found:
            state.block_found = False;
            state.active = False;
            time.sleep(0.3)
            for mt in miner_threads:
                if mt.thread and mt.thread.is_alive(): mt.thread.join(timeout=2)
            miner_threads.clear()
            chain = safe_request(f"{state.get_node_url()}/chain")
            if chain:
                with state.template_lock:
                    state.height = chain["length"];
                    state.prev_hash = chain["chain"][-1]["hash"]
                    state.target = chain.get("current_target", 0);
                    state.reward = 10.0 / (2 ** (state.height // 876000))
                    state.txs = safe_request(f"{state.get_node_url()}/pending") or [];
                    state.template_version += 1
            state.active = True
            if state.pool_mode:
                for tid in range(threads):
                    pt = PoolThread(tid, address);
                    t = threading.Thread(target=pt.run, daemon=True, name=f"p-{tid}")
                    t.start();
                    pt.thread = t;
                    miner_threads.append(pt)
            else:
                for tid in range(threads):
                    mt = MinerThread(tid, address, priv_hex);
                    t = threading.Thread(target=mt.run, daemon=True, name=f"m-{tid}")
                    t.start();
                    mt.thread = t;
                    miner_threads.append(mt)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal: {e}"); traceback.print_exc(); sys.exit(1)