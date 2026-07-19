#!/usr/bin/env python3
"""
RAMCOIN POOL MINER v1.0.0 - GENESIS EDITION
Ramhash v7 - Memory-hard CPU mining - Pool mode
"""
import hashlib
import json
import os
import sys
import time
import array
import signal
import secrets
import threading
import logging
import traceback
from typing import Tuple, Optional, Dict
import urllib.request
import urllib.error

# ==================== CONSTANTS ====================
VERSION = "1.0.0"
COIN = 100_000_000
MAX_TARGET = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
SCRATCHPAD_ITER = 8192
BASE_SCRATCHPAD = 524288
MAX_SCRATCHPAD = 4194304
MAX_THREADS_PER_MINER = 4
EXPECTED_MODS = SCRATCHPAD_ITER + (SCRATCHPAD_ITER // 256) + (SCRATCHPAD_ITER // 50000)

# ==================== COLORS ====================
GR = '\033[92m'
CY = '\033[96m'
YE = '\033[93m'
RE = '\033[91m'
BO = '\033[1m'
NC = '\033[0m'

# ==================== SETTINGS ====================
NODES = ["http://127.0.0.1:5000", "http://90.188.115.169:5000"]

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('POOL')


# ==================== HTTP CLIENT ====================
def http_get(path: str, timeout: int = 10) -> Optional[Dict]:
    for node in NODES:
        try:
            url = f"{node}{path}"
            req = urllib.request.Request(url, headers={"Connection": "close"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except:
            pass
    return None


def http_post(path: str, data, timeout: int = 10) -> Optional[Dict]:
    for node in NODES:
        try:
            url = f"{node}{path}"
            body = json.dumps(data).encode()
            headers = {
                "Content-Type": "application/json",
                "Connection": "close"
            }
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except:
            pass
    return None


# ==================== POW FUNCTIONS ====================
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


# ==================== FORMATTERS ====================
def fmt_speed(hashes_per_sec: float) -> str:
    if hashes_per_sec >= 1_000_000_000:
        return f"{hashes_per_sec / 1_000_000_000:.2f} GRam/s"
    elif hashes_per_sec >= 1_000_000:
        return f"{hashes_per_sec / 1_000_000:.2f} MRam/s"
    elif hashes_per_sec >= 1_000:
        return f"{hashes_per_sec / 1_000:.2f} KRam/s"
    else:
        return f"{hashes_per_sec:.0f} Ram/s"


def fmt_diff(target: int) -> str:
    if target <= 0:
        return "inf"
    sd = MAX_TARGET / target
    if sd >= 1e12: return f"{sd / 1e12:.2f} TRam/s"
    if sd >= 1e9:  return f"{sd / 1e9:.2f} GRam/s"
    if sd >= 1e6:  return f"{sd / 1e6:.2f} MRam/s"
    if sd >= 1e3:  return f"{sd / 1e3:.2f} KRam/s"
    return f"{sd:.2f} Ram/s"


# ==================== POOL MINER ====================
class PoolMiner:
    def __init__(self, address: str, num_threads: int = 4):
        self.address = address
        self.num_threads = min(num_threads, MAX_THREADS_PER_MINER)

        self.lock = threading.Lock()
        self.current_height = -1
        self.current_prev_hash = ""
        self.current_pool_target = MAX_TARGET

        self.total_hashes = 0
        self.pool_shares = 0
        self.start_time = time.time()
        self.node_ok = True

        self.stop_event = threading.Event()

    def update_pool_info(self) -> bool:
        try:
            tmpl = http_get("/pool/template", timeout=5)
            if not tmpl:
                self.node_ok = False
                return False

            self.node_ok = True
            height = tmpl.get("height", 0)
            prev_hash = tmpl.get("previous_hash", "")
            pool_target = tmpl.get("pool_target", MAX_TARGET)

            with self.lock:
                if height != self.current_height:
                    self.current_height = height
                    self.current_prev_hash = prev_hash
                    self.current_pool_target = pool_target
                else:
                    self.current_height = height
                    self.current_prev_hash = prev_hash
                    self.current_pool_target = pool_target

            return True
        except:
            self.node_ok = False
            return False

    def mine_shares(self, thread_id: int) -> None:
        nonce = secrets.randbits(48)
        nseed = secrets.randbits(32)
        buffer_size = BASE_SCRATCHPAD
        last_height = -1
        sp = None
        seed = 0
        last_share_time = 0

        while not self.stop_event.is_set():
            try:
                with self.lock:
                    if self.current_height < 0:
                        time.sleep(0.1)
                        continue
                    height = self.current_height
                    prev_hash = self.current_prev_hash
                    pool_target = self.current_pool_target

                if height != last_height:
                    last_height = height
                    sp, seed = create_scratchpad_sync(prev_hash, thread_id, nseed, buffer_size)
                    nonce = secrets.randbits(48)

                batch_size = 500
                for _ in range(batch_size):
                    if self.stop_event.is_set():
                        break
                    with self.lock:
                        if self.current_height != height:
                            break

                    mix, new_nseed, mods = memhard_sync(sp, seed, nonce, nseed, buffer_size)
                    with self.lock:
                        self.total_hashes += 1

                    if mods != EXPECTED_MODS:
                        nonce = (nonce + 1) & 0xFFFFFFFFFFFF
                        continue

                    proof = hashlib.sha256(f"{mix}{prev_hash}{new_nseed}{mods}".encode()).hexdigest()
                    proof_int = int(proof, 16)

                    if proof_int <= pool_target:
                        now = time.time()
                        if now - last_share_time >= 0.5:
                            last_share_time = now
                            share_data = {
                                "miner_address": self.address,
                                "nonce": int(nonce),
                                "nonce_seed": int(new_nseed),
                                "mix": str(mix),
                                "mods": mods,
                                "extra_nonce": thread_id,
                                "scratchpad_size": buffer_size
                            }
                            resp = http_post("/pool/share", share_data, timeout=5)
                            if resp and resp.get("status") == "ok":
                                with self.lock:
                                    self.pool_shares += 1

                    nonce = (nonce + 1) & 0xFFFFFFFFFFFF
                    if nonce > 2 ** 50:
                        nonce = secrets.randbits(48)
                        nseed = secrets.randbits(32)

            except Exception as e:
                log.error(f"Thread {thread_id} error: {e}")
                time.sleep(1)
                nonce = secrets.randbits(48)
                nseed = secrets.randbits(32)

    def poller(self) -> None:
        while not self.stop_event.is_set():
            self.update_pool_info()
            time.sleep(2)

    def logger(self) -> None:
        last_hashes = 0
        last_time = time.time()

        while not self.stop_event.is_set():
            time.sleep(3)
            if self.current_height < 0:
                continue

            now = time.time()
            with self.lock:
                current_hashes = self.total_hashes
                height = self.current_height
                pool_target = self.current_pool_target
                shares = self.pool_shares

            dt = now - last_time
            dh = current_hashes - last_hashes
            speed = dh / dt if dt > 0 else 0
            last_hashes = current_hashes
            last_time = now

            speed_str = fmt_speed(speed)
            diff_str = fmt_diff(pool_target)

            uptime = int(time.time() - self.start_time)
            hh, mm, ss = uptime // 3600, (uptime % 3600) // 60, uptime % 60

            node_str = f"{GR}OK{NC}" if self.node_ok else f"{RE}DOWN{NC}"

            log.info(
                f"[{hh:02d}:{mm:02d}:{ss:02d}] {CY}{BO}POOL{NC} {BO}{speed_str}{NC} | "
                f"Block:{CY}#{height}{NC} | "
                f"Diff:{diff_str} | "
                f"Shares:{GR}{shares}{NC} | "
                f"Node:{node_str}"
            )

    def run(self) -> None:
        log.info(f"{BO}========================================{NC}")
        log.info(f"{BO}  RAMCOIN POOL MINER v{VERSION}{NC}")
        log.info(f"{BO}========================================{NC}")

        log.info("Syncing with pool...")
        if not self.update_pool_info():
            log.error(f"{RE}Failed to sync with pool!{NC}")
            sys.exit(1)

        diff_str = fmt_diff(self.current_pool_target)

        log.info(f"Ready! Block #{self.current_height} | Pool Diff: {diff_str}")
        log.info(f"Using {self.num_threads} threads (MAX: {MAX_THREADS_PER_MINER})")
        log.info(f"Address: {self.address}")
        log.info(f"{CY}{BO}POOL MINING STARTED!{NC}")

        threading.Thread(target=self.poller, daemon=True).start()
        threading.Thread(target=self.logger, daemon=True).start()

        for tid in range(self.num_threads):
            threading.Thread(target=self.mine_shares, args=(tid,), daemon=True).start()

        log.info(f"{GR}{self.num_threads} mining threads started{NC}")

        def stop_handler(sig, frame):
            log.info(f"{YE}Stopping...{NC}")
            self.stop_event.set()
            time.sleep(2)

            elapsed = time.time() - self.start_time
            log.info(f"\n{BO}========================================{NC}")
            log.info(f"{BO}  MINING SUMMARY{NC}")
            log.info(f"{BO}========================================{NC}")
            log.info(f"  Runtime:      {elapsed:.0f}s")
            log.info(f"  Shares found: {GR}{self.pool_shares}{NC}")
            log.info(f"  Total hashes: {self.total_hashes:,}")
            if elapsed > 0:
                log.info(f"  Avg speed:    {fmt_speed(self.total_hashes / elapsed)}")
            log.info(f"{BO}========================================{NC}")
            sys.exit(0)

        signal.signal(signal.SIGINT, stop_handler)
        signal.signal(signal.SIGTERM, stop_handler)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_handler(None, None)


def main():
    health = http_get("/health", timeout=3)
    if not health or not health.get("ok"):
        log.error(f"{RE}Node offline!{NC}")
        sys.exit(1)

    log.info(f"Node: v{health.get('version', '?')} H:#{health.get('height', '?')}")

    threads = min(os.cpu_count() or 4, MAX_THREADS_PER_MINER)
    log.info(f"Using {threads} threads (MAX: {MAX_THREADS_PER_MINER})\n")

    address = input("RAM_ address: ").strip()
    if not address.startswith("RAM_"):
        log.error(f"{RE}Invalid address! Must start with RAM_{NC}")
        sys.exit(1)

    miner = PoolMiner(address, threads)
    miner.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.critical(f"{RE}Fatal error: {e}{NC}")
        traceback.print_exc()
        sys.exit(1)