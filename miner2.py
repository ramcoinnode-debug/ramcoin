#!/usr/bin/env python3
"""
RAMCOIN MINER v7.1.0 - COMPATIBILITY FIX
Совместим с нодой v9.0.15 / v10.2.0 (PROTOCOL 2)
"""

import hashlib, json, os, sys, time, array, signal, traceback, secrets, threading
from collections import OrderedDict
import urllib.request
import urllib.error

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from hashlib import pbkdf2_hmac
from Crypto.Cipher import AES
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

VERSION = "7.1.0"
COIN = 100_000_000
MAX_TARGET = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
SCRATCHPAD_ITER = 8192
BASE_SCRATCHPAD = 524288
PROTOCOL = 2

NODES = [
    "http://127.0.0.1:5000",
    "http://90.188.115.169:5000",
]

NODE_TIMEOUT = 5
SUBMIT_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2
SPEED_SMOOTHING = 0.85
SPEED_UPDATE_INTERVAL = 0.3
LOG_INTERVAL = 10
POLL_INTERVAL = 2
THREAD_TIMEOUT = 300
MAX_NODE_FAILS = 10


class MinerState:
    def __init__(self):
        self.lock = threading.RLock()
        self.height = -1
        self.prev_hash = ""
        self.target = 0
        self.reward = 10.0
        self.txs = []
        self.active = False
        self.block_found_event = threading.Event()
        self.node_ok = False
        self.node_url = None
        self.node_fails = 0
        self.mined = 0
        self.total_ram = 0.0
        self.rejected = 0
        self.start_time = time.time()
        self.speed = 0.0
        self.thread_speeds = {}
        self.thread_updates = {}
        self.thread_last_active = {}
        self.template_version = 0
        self.template_lock = threading.RLock()
        self.current_buffer_size = BASE_SCRATCHPAD
        self.pool_mode = False
        self.pool_shares = 0

    def update_speed(self, tid, sols):
        with self.lock:
            now = time.time()
            last = self.thread_updates.get(tid, now - 1)
            elapsed = max(0.01, now - last)
            instant = sols / elapsed
            self.speed = instant if self.speed == 0 else self.speed * SPEED_SMOOTHING + instant * (1 - SPEED_SMOOTHING)
            self.thread_speeds[tid] = instant
            self.thread_updates[tid] = now
            self.thread_last_active[tid] = now

    def get_template(self):
        with self.template_lock:
            return (self.height, self.prev_hash, self.target, self.reward, self.txs,
                    self.template_version, self.current_buffer_size)

    def check_node_health(self):
        if self.node_fails >= MAX_NODE_FAILS:
            return False
        return True

    def signal_block_found(self):
        self.block_found_event.set()

    def clear_block_found(self):
        self.block_found_event.clear()


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
    for attempt in range(max_retries):
        try:
            if data is None:
                req = urllib.request.Request(url, headers={"Connection": "close"})
            else:
                req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                             headers={"Content-Type": "application/json", "Connection": "close"},
                                             method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.loads(r.read().decode())
                if resp is None:
                    raise ValueError("Empty response")
                state.node_fails = 0
                return resp
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
            else:
                state.node_fails += 1
    return None


def find_best_node():
    print("🔍 Поиск ноды...")
    for url in NODES:
        try:
            print(f"   Проверяю {url}...")
            resp = safe_request(f"{url}/health", timeout=3, max_retries=1)
            if resp and resp.get("ok"):
                height = resp.get("height", 0)
                version = resp.get("version", "")
                if height > 0:
                    print(f"✅ Нода найдена: {url} (H=#{height}, v{version})")
                    state.node_fails = 0
                    return url
        except:
            pass
    print("❌ Ноды не найдены. Повтор через 5 сек...")
    time.sleep(5)
    return find_best_node()


def http_poller():
    last_height = -1
    while True:
        try:
            time.sleep(POLL_INTERVAL)
            if not state.node_url or not state.check_node_health():
                print("⚠️ Потеря связи с нодой, ищу новую...")
                state.node_url = find_best_node()
                continue
            chain = safe_request(f"{state.node_url}/chain", timeout=5)
            if not chain or not isinstance(chain, dict):
                state.node_fails += 1
                continue
            current_height = chain.get("length", chain.get("height", 0))
            if current_height <= 0:
                state.node_fails += 1
                continue
            if current_height != last_height and current_height > 0:
                last_height = current_height
                with state.template_lock:
                    state.height = current_height
                    chain_data = chain.get("chain", [])
                    if chain_data:
                        state.prev_hash = chain_data[-1].get("hash", "")
                    state.target = chain.get("current_target", chain.get("target", 0))
                    if state.target > 0:
                        state.reward = 10.0 / (2 ** (state.height // 876000))
                        state.txs = safe_request(f"{state.node_url}/pending") or []
                        state.template_version += 1
                        state.signal_block_found()
        except Exception as e:
            state.node_fails += 1
            time.sleep(1)


def sign_block(block, priv_hex):
    try:
        priv = ec.derive_private_key(int(priv_hex, 16), ec.SECP256K1())
        data = OrderedDict([
            ("v", PROTOCOL),
            ("i", block["index"]),
            ("ph", block["previous_hash"]),
            ("t", block["timestamp"]),
            ("n", block["nonce"]),
            ("ns", block.get("nonce_seed", 0)),
            ("mp", block["memory_proof"]),
            ("ma", block.get("miner_payout_address", "")),
            ("sm", block.get("scratchpad_mods", 0)),
            ("ss", block["scratchpad_size"]),
            ("en", block.get("extra_nonce", 0))
        ])
        hash_bytes = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).digest()
        return priv.sign(hash_bytes, ec.ECDSA(hashes.SHA256())).hex()
    except:
        return None


def create_scratchpad(prev_hash, tid, nseed, buffer_size=None):
    size = buffer_size or BASE_SCRATCHPAD
    sp = array.array('Q', [0]) * size
    seed_str = f"{prev_hash}|{tid}|{nseed}|RAMCOIN_v7|{size}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
    s0, s1 = seed, seed ^ 0xDEADBEEF
    for i in range(size):
        s1, s0 = s0 & 0xFFFFFFFFFFFFFFFF, s1
        s1 ^= (s1 << 23) & 0xFFFFFFFFFFFFFFFF
        s1 ^= (s1 >> 17)
        s1 ^= s0
        s1 ^= (s0 >> 26)
        sp[i] = (s0 + s1) & 0xFFFFFFFFFFFFFFFF
    return sp, seed, size


def memhard_loop(sp, seed, nonce, nseed, buffer_size=None):
    size = buffer_size or BASE_SCRATCHPAD
    sp_copy = array.array('Q', sp)
    mix = seed
    mods = 0
    nseed_current = nseed
    for k in range(SCRATCHPAD_ITER):
        if k & 63 == 0:
            if not state.active or state.block_found_event.is_set():
                return None, None, None
        mix = (mix * 0x9E3779B97F4A7C15 + nonce + nseed_current) & 0xFFFFFFFFFFFFFFFF
        mix ^= (mix >> 33)
        mix ^= (mix << 13)
        idx = mix % size
        rv = sp_copy[idx]
        sp_copy[idx] = (rv ^ mix ^ nonce) & 0xFFFFFFFFFFFFFFFF
        mods += 1
        mix = (mix + rv) & 0xFFFFFFFFFFFFFFFF
        if k % 256 == 0:
            idx2 = ((idx * 1103515245 + 12345) ^ rv) % size
            sp_copy[idx2] = (sp_copy[idx2] ^ (mix >> 16) ^ nonce) & 0xFFFFFFFFFFFFFFFF
            mods += 1
        if k > 0 and k % 50000 == 0:
            nseed_current = (nseed_current + 1) & 0xFFFFFFFF
            mix = (mix ^ nseed_current) & 0xFFFFFFFFFFFFFFFF
    return mix, nseed_current, mods


def verify_solution(prev_hash, nonce, nseed, mix, mods, target):
    try:
        proof = hashlib.sha256(f"{mix}{prev_hash}{nseed}{mods}".encode()).hexdigest()
        return int(proof, 16) <= target, proof
    except:
        return False, ""


def check_thread_timeout(tid):
    last_active = state.thread_last_active.get(tid, time.time())
    if time.time() - last_active > THREAD_TIMEOUT:
        print(f"⚠️ Поток {tid} завис! Перезапуск...")
        return True
    return False


class MinerThread:
    def __init__(self, tid, address, priv_key):
        self.tid = tid
        self.address = address
        self.priv_key = priv_key
        self.nonce = secrets.randbits(32)
        self.nseed = secrets.randbits(16)
        self.iterations = 0
        self.last_restart = time.time()
        self.thread = None

    def run(self):
        if HAS_PSUTIL:
            try:
                p = psutil.Process()
                phys = psutil.cpu_count(logical=False) or 1
                os.sched_setaffinity(0, {self.tid % phys})
            except:
                pass
        state.thread_last_active[self.tid] = time.time()
        self.last_restart = time.time()
        while state.active:
            try:
                self._mine_loop()
            except Exception as e:
                time.sleep(1)
            self.nonce = secrets.randbits(32)
            self.nseed = secrets.randbits(16)
            if check_thread_timeout(self.tid):
                self.last_restart = time.time()

    def _mine_loop(self):
        height, prev_hash, target, reward, txs, tpl_ver, buf_size = state.get_template()
        if height < 0:
            time.sleep(1)
            return
        original_nseed = self.nseed
        try:
            sp, seed, actual_size = create_scratchpad(prev_hash, self.tid, self.nseed, buf_size)
        except:
            time.sleep(0.5)
            return
        local_sol = 0
        last_report = time.time()
        while state.active and not state.block_found_event.is_set():
            if time.time() - self.last_restart > THREAD_TIMEOUT:
                self.nonce = secrets.randbits(32)
                self.nseed = secrets.randbits(16)
                original_nseed = self.nseed
                self.last_restart = time.time()
                try:
                    sp, seed, actual_size = create_scratchpad(prev_hash, self.tid, self.nseed, buf_size)
                except:
                    return
            cur = state.get_template()
            if cur[5] != tpl_ver:
                height, prev_hash, target, reward, txs, tpl_ver, buf_size = cur
                try:
                    sp, seed, actual_size = create_scratchpad(prev_hash, self.tid, self.nseed, buf_size)
                except:
                    return
                self.nonce = secrets.randbits(32)
                self.nseed = secrets.randbits(16)
                original_nseed = self.nseed
                tpl_ver = cur[5]
            try:
                mix, new_nseed, mods = memhard_loop(sp, seed, self.nonce, self.nseed, actual_size)
                if mix is None:
                    return
                local_sol += 1
                self.iterations += 1
                now = time.time()
                if now - last_report >= SPEED_UPDATE_INTERVAL:
                    state.update_speed(self.tid, local_sol)
                    local_sol = 0
                    last_report = now
                is_valid, proof = verify_solution(prev_hash, self.nonce, new_nseed, mix, mods, target)
                if is_valid:
                    with state.lock:
                        if state.block_found_event.is_set() or state.height != height:
                            return
                        state.signal_block_found()
                    block = {
                        "index": height,
                        "previous_hash": prev_hash,
                        "transactions": txs,
                        "timestamp": int(time.time()),
                        "nonce": int(self.nonce),
                        "nonce_seed": int(original_nseed),
                        "memory_proof": proof,
                        "target": target,
                        "extra_nonce": self.tid,
                        "miner_payout_address": self.address,
                        "scratchpad_mods": mods,
                        "scratchpad_size": actual_size,
                        "pool_block": False,
                        "threads_used": 4  # 🔥 добавить
                    }
                    sig = sign_block(block, self.priv_key)
                    if not sig:
                        state.clear_block_found()
                        self.nonce = secrets.randbits(32)
                        continue
                    block["miner_signature"] = sig
                    if not state.check_node_health():
                        state.node_url = find_best_node()
                    resp = safe_request(f"{state.node_url}/mine", block, timeout=SUBMIT_TIMEOUT)
                    if resp and isinstance(resp, dict) and resp.get("status") == "ok":
                        state.mined += 1
                        state.total_ram += reward
                        print(f"[{fmt_time(time.time() - state.start_time)}] 🎉 BLOCK #{height} ACCEPTED +{reward:.2f} RAM")
                    else:
                        state.rejected += 1
                        state.clear_block_found()
                        reason = resp.get("reason", "unknown") if resp and isinstance(resp, dict) else "invalid response"
                        print(f"[{fmt_time(time.time() - state.start_time)}] ❌ BLOCK #{height} REJECTED: {reason}")
                    return
                self.nonce = (self.nonce + 1) & 0xFFFFFFFF
                if self.nonce > 2 ** 48:
                    self.nonce = secrets.randbits(32)
                    self.nseed = secrets.randbits(16)
                    original_nseed = self.nseed
            except:
                self.nonce = secrets.randbits(32)
                time.sleep(0.1)


class PoolThread:
    def __init__(self, tid, address):
        self.tid = tid
        self.address = address
        self.nonce = secrets.randbits(32)
        self.nseed = secrets.randbits(16)
        self.last_restart = time.time()
        self.thread = None

    def run(self):
        if HAS_PSUTIL:
            try:
                p = psutil.Process()
                phys = psutil.cpu_count(logical=False) or 1
                os.sched_setaffinity(0, {self.tid % phys})
            except:
                pass
        state.thread_last_active[self.tid] = time.time()
        while state.active:
            try:
                self._pool_loop()
            except:
                time.sleep(1)
            self.nonce = secrets.randbits(32)
            self.nseed = secrets.randbits(16)
            if check_thread_timeout(self.tid):
                self.last_restart = time.time()

    def _pool_loop(self):
        while state.active and not state.block_found_event.is_set():
            if not state.node_url or not state.check_node_health():
                state.node_url = find_best_node()
                time.sleep(1)
                continue
            tmpl = safe_request(f"{state.node_url}/pool/template", timeout=5)
            if not tmpl or not isinstance(tmpl, dict) or "previous_hash" not in tmpl:
                time.sleep(2)
                continue
            prev_hash = tmpl["previous_hash"]
            pool_target = tmpl.get("pool_target", MAX_TARGET)
            original_nseed = self.nseed
            try:
                sp, seed, actual_size = create_scratchpad(prev_hash, self.tid, self.nseed)
            except:
                time.sleep(0.5)
                continue
            local_sol = 0
            last_report = time.time()
            while state.active and not state.block_found_event.is_set():
                if time.time() - self.last_restart > THREAD_TIMEOUT:
                    break
                try:
                    mix, new_nseed, mods = memhard_loop(sp, seed, self.nonce, self.nseed, actual_size)
                    if mix is None:
                        return
                    local_sol += 1
                    now = time.time()
                    if now - last_report >= SPEED_UPDATE_INTERVAL:
                        state.update_speed(self.tid, local_sol)
                        local_sol = 0
                        last_report = now
                    is_share, _ = verify_solution(prev_hash, self.nonce, new_nseed, mix, mods, pool_target)
                    if is_share:
                        share_data = {
                            "miner_address": self.address,
                            "nonce": int(self.nonce),
                            "nonce_seed": int(original_nseed),
                            "mix": str(mix),
                            "mods": mods,
                            "extra_nonce": self.tid,
                            "scratchpad_size": actual_size,
                            "threads_used": 4  # 🔥 ВОТ СЮДА
                        }
                        resp = safe_request(f"{state.node_url}/pool/share", share_data, timeout=5)
                        if resp and isinstance(resp, dict) and resp.get("status") == "ok":
                            state.pool_shares += 1
                    self.nonce = (self.nonce + 1) & 0xFFFFFFFF
                    if self.nonce > 2 ** 48:
                        self.nonce = secrets.randbits(32)
                        self.nseed = secrets.randbits(16)
                        original_nseed = self.nseed
                except:
                    self.nonce = secrets.randbits(32)
                    time.sleep(0.1)


def logger():
    last_log = 0
    while True:
        time.sleep(1)
        now = time.time()
        if now - last_log >= LOG_INTERVAL:
            s = state
            mode = "POOL" if s.pool_mode else "SOLO"
            shares_info = f"Shares: {s.pool_shares}" if s.pool_mode else ""
            print(f"[{fmt_time(time.time() - s.start_time)}] {mode} | {fmt_speed(s.speed)} | "
                  f"Blocks: {s.mined} | Rejected: {s.rejected} | {shares_info} | "
                  f"H:#{s.height} | R:{s.reward:.2f}", flush=True)
            last_log = now


def load_wallet():
    for wf in ["ramcoin_wallet.json", "wallet.json"]:
        if not os.path.exists(wf):
            continue
        try:
            with open(wf) as f:
                data = json.load(f)
            if "private_key_hex" in data and len(data["private_key_hex"]) == 64 and data.get("address", "").startswith("RAM_"):
                return data["private_key_hex"], data["address"]
            if "crypto_data" in data:
                for i in range(3):
                    pw = input(f"Password ({i + 1}/3): ").strip()
                    if not pw:
                        continue
                    try:
                        raw = bytes.fromhex(data["crypto_data"])
                        key = pbkdf2_hmac('sha512', pw.encode(), raw[:32], 600000, dklen=32)
                        cipher = AES.new(key, AES.MODE_GCM, nonce=raw[32:48])
                        dec = json.loads(cipher.decrypt_and_verify(raw[64:], raw[48:64]))
                        if len(dec["private_key_hex"]) == 64 and dec["address"].startswith("RAM_"):
                            return dec["private_key_hex"], dec["address"]
                    except:
                        pass
        except:
            pass
    return None, None


def main():
    print(f"╔══════════════════════════════════════╗")
    print(f"║   RAMCOIN MINER v{VERSION} - FIXED   ║")
    print(f"║   Совместимость, стабильность       ║")
    print(f"╚══════════════════════════════════════╝")
    threads = max(1, (os.cpu_count() or 2) // 2)
    print(f"Threads: {threads}")
    print(f"\nSelect mode:")
    print(f"  1. SOLO mining")
    print(f"  2. POOL mining")
    while True:
        c = input(f"Choose [1/2]: ").strip()
        if c in ("1", "2"):
            break
    pool_mode = (c == "2")
    print(f"Mode: {'POOL' if pool_mode else 'SOLO'}\n")
    priv_hex, address = load_wallet()
    if not priv_hex:
        print("❌ Wallet not found!")
        sys.exit(1)
    print(f"✅ Wallet loaded: {address[:42]}...\n")
    state.node_url = find_best_node()
    print(f"📍 Используется нода: {state.node_url}\n")
    print("🔄 Синхронизация...")
    chain = safe_request(f"{state.node_url}/chain")
    if not chain or not isinstance(chain, dict):
        print("❌ Не могу получить блокчейн!")
        sys.exit(1)
    with state.template_lock:
        state.height = chain.get("length", chain.get("height", 0))
        chain_data = chain.get("chain", [])
        if chain_data:
            state.prev_hash = chain_data[-1].get("hash", "")
        state.target = chain.get("current_target", chain.get("target", 0))
        if state.target <= 0:
            print("❌ Невалидный target!")
            sys.exit(1)
        state.reward = 10.0 / (2 ** (state.height // 876000))
        state.txs = safe_request(f"{state.node_url}/pending") or []
        state.template_version = 1
    state.active = True
    state.pool_mode = pool_mode
    print(f"✅ Connected! H:#{state.height} | Reward: {state.reward} RAM")
    print(f"🚀 {'POOL' if pool_mode else 'SOLO'} MINING STARTED!\n")
    threading.Thread(target=logger, daemon=True).start()
    threading.Thread(target=http_poller, daemon=True).start()

    def sig_handler(sig, frame):
        print(f"\n⏹️  Stopping...")
        print(f"Blocks: {state.mined} | RAM: {state.total_ram:.4f} | Rejected: {state.rejected} | Shares: {state.pool_shares}")
        state.active = False
        state.signal_block_found()
        time.sleep(0.5)
        sys.exit(0)
    signal.signal(signal.SIGINT, sig_handler)
    miner_threads = []
    if pool_mode:
        for tid in range(threads):
            pt = PoolThread(tid, address)
            t = threading.Thread(target=pt.run, daemon=True, name=f"p-{tid}")
            t.start()
            pt.thread = t
            miner_threads.append(pt)
    else:
        for tid in range(threads):
            mt = MinerThread(tid, address, priv_hex)
            t = threading.Thread(target=mt.run, daemon=True, name=f"m-{tid}")
            t.start()
            mt.thread = t
            miner_threads.append(mt)

    def watchdog():
        while state.active:
            time.sleep(30)
            for mt in miner_threads:
                if mt.tid in state.thread_last_active:
                    if time.time() - state.thread_last_active[mt.tid] > THREAD_TIMEOUT:
                        print(f"⚠️ Поток {mt.tid} завис! Потоки будут перезапущены при следующем блоке")
    threading.Thread(target=watchdog, daemon=True).start()
    while True:
        time.sleep(1)
        if state.block_found_event.is_set():
            state.clear_block_found()
            state.active = False
            time.sleep(0.3)
            for mt in miner_threads:
                if mt.thread and mt.thread.is_alive():
                    mt.thread.join(timeout=2)
            miner_threads.clear()
            if not state.check_node_health():
                state.node_url = find_best_node()
            chain = safe_request(f"{state.node_url}/chain")
            if chain and isinstance(chain, dict):
                with state.template_lock:
                    state.height = chain.get("length", chain.get("height", 0))
                    chain_data = chain.get("chain", [])
                    if chain_data:
                        state.prev_hash = chain_data[-1].get("hash", "")
                    state.target = chain.get("current_target", chain.get("target", 0))
                    state.reward = 10.0 / (2 ** (state.height // 876000))
                    state.txs = safe_request(f"{state.node_url}/pending") or []
                    state.template_version += 1
            state.active = True
            if pool_mode:
                for tid in range(threads):
                    pt = PoolThread(tid, address)
                    t = threading.Thread(target=pt.run, daemon=True, name=f"p-{tid}")
                    t.start()
                    pt.thread = t
                    miner_threads.append(pt)
            else:
                for tid in range(threads):
                    mt = MinerThread(tid, address, priv_hex)
                    t = threading.Thread(target=mt.run, daemon=True, name=f"m-{tid}")
                    t.start()
                    mt.thread = t
                    miner_threads.append(mt)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"❌ Fatal: {e}")
        traceback.print_exc()
        sys.exit(1)