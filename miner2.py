#!/usr/bin/env python3
"""
RAMCOIN MINER v30.0.3 - FIXED THREADS LIMIT
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
import gc
import logging
import traceback
from typing import Tuple, Optional, List, Dict, Any
from collections import OrderedDict
import urllib.request
import urllib.error
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

# ==================== КОНСТАНТЫ ====================
VERSION = "30.0.3"
COIN = 100_000_000
MAX_TARGET = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
SCRATCHPAD_ITER = 8192
BASE_SCRATCHPAD = 524288
MAX_SCRATCHPAD = 4194304
MAX_THREADS_PER_MINER = 4  # ВАЖНО: нода проверяет это значение!
PROTOCOL = 2
EXPECTED_MODS = SCRATCHPAD_ITER + (SCRATCHPAD_ITER // 256) + (SCRATCHPAD_ITER // 50000)

# ==================== ЦВЕТА ====================
GR = '\033[92m'
CY = '\033[96m'
YE = '\033[93m'
RE = '\033[91m'
BO = '\033[1m'
NC = '\033[0m'

# ==================== НАСТРОЙКИ ====================
API_KEY_FILE = "api_key.txt"
NODES = ["http://127.0.0.1:5000", "http://90.188.115.169:5000"]

# ==================== ЛОГГИРОВАНИЕ ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('MINER')


# ==================== HTTP КЛИЕНТ ====================
def http_get(path: str, timeout: int = 10) -> Optional[Dict]:
    for node in NODES:
        try:
            url = f"{node}{path}"
            req = urllib.request.Request(url, headers={"Connection": "close"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            log.debug(f"HTTP GET error for {node}: {e}")
    return None


def http_post(path: str, data: dict, timeout: int = 10) -> Optional[Dict]:
    api_key = open(API_KEY_FILE).read().strip() if os.path.exists(API_KEY_FILE) else ""
    for node in NODES:
        try:
            url = f"{node}{path}"
            body = json.dumps(data).encode()
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": api_key,
                "Connection": "close"
            }
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            log.debug(f"HTTP POST error for {node}: {e}")
    return None


# ==================== PoW - ТОЧНАЯ КОПИЯ ФУНКЦИЙ НОДЫ ====================
def create_scratchpad_sync(prev_hash, tid, nseed, buffer_size):
    """
    ТОЧНАЯ КОПИЯ из ноды
    """
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


def memhard_sync(sp, seed, nonce, nseed, buffer_size):
    """
    ТОЧНАЯ КОПИЯ из ноды
    """
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


def verify_pow_sync(block, target):
    """
    ТОЧНАЯ КОПИЯ из ноды
    """
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
        expected = SCRATCHPAD_ITER + (SCRATCHPAD_ITER // 256) + (SCRATCHPAD_ITER // 50000)
        if mods != expected:
            return False
        proof = hashlib.sha256(
            f"{mix}{block['previous_hash']}{new_nseed}{mods}".encode()
        ).hexdigest()
        return int(proof, 16) <= target
    except:
        return False


# ==================== ПОДПИСЬ БЛОКА ====================
def sign_block(block: dict, private_key_hex: str) -> Optional[str]:
    try:
        private_key = ec.derive_private_key(int(private_key_hex, 16), ec.SECP256K1())

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
            ("ss", block.get("scratchpad_size", BASE_SCRATCHPAD)),
            ("en", block.get("extra_nonce", 0))
        ])

        hash_bytes = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).digest()
        signature = private_key.sign(hash_bytes, ec.ECDSA(hashes.SHA256()))
        return signature.hex()
    except Exception as e:
        log.error(f"Sign error: {e}")
        return None


# ==================== МАЙНЕР ====================
class RamcoinMiner:
    def __init__(self, address: str, private_key: str, pool_mode: bool = False, num_threads: int = 4):
        self.address = address
        self.private_key = private_key
        self.pool_mode = pool_mode
        # Ограничиваем потоки до MAX_THREADS_PER_MINER
        self.num_threads = min(num_threads, MAX_THREADS_PER_MINER)

        self.lock = threading.Lock()
        self.current_height = -1
        self.current_prev_hash = ""
        self.current_target = MAX_TARGET
        self.current_pool_target = MAX_TARGET
        self.current_reward = 10.0
        self.current_transactions = []

        self.total_hashes = 0
        self.blocks_mined = 0
        self.blocks_rejected = 0
        self.total_reward = 0.0
        self.pool_shares = 0
        self.start_time = time.time()
        self.node_ok = True

        self.stop_event = threading.Event()
        self.block_found = threading.Event()

    def update_block_info(self) -> bool:
        try:
            chain = http_get("/chain", timeout=5)
            if not chain:
                self.node_ok = False
                return False

            self.node_ok = True
            height = chain.get("length", chain.get("height", 0))
            if height <= 0:
                return False

            chain_data = chain.get("chain", [])
            prev_hash = chain_data[-1].get("hash", "") if chain_data else ""
            target = chain.get("current_target", chain.get("target", MAX_TARGET))
            pool_target = min(MAX_TARGET, int(target * 100)) if target > 0 else MAX_TARGET
            reward = chain.get("reward", 10.0)
            transactions = http_get("/pending", timeout=5) or []

            with self.lock:
                self.current_height = height
                self.current_prev_hash = prev_hash
                self.current_target = target
                self.current_pool_target = pool_target
                self.current_reward = reward
                self.current_transactions = transactions

            self.block_found.clear()
            return True

        except Exception as e:
            log.debug(f"Update error: {e}")
            self.node_ok = False
            return False

    def mine_block(self, thread_id: int) -> None:
        """Поток майнинга"""
        nonce = secrets.randbits(48)
        nseed = secrets.randbits(32)
        buffer_size = BASE_SCRATCHPAD
        last_height = -1
        sp = None
        seed = 0

        while not self.stop_event.is_set():
            try:
                with self.lock:
                    if self.current_height < 0 or self.block_found.is_set():
                        time.sleep(0.1)
                        continue

                    height = self.current_height
                    prev_hash = self.current_prev_hash
                    target = self.current_target
                    pool_target = self.current_pool_target

                # Создаем scratchpad только при смене блока
                if height != last_height:
                    last_height = height
                    sp, seed = create_scratchpad_sync(prev_hash, thread_id, nseed, buffer_size)
                    nonce = secrets.randbits(48)

                # Основной цикл майнинга
                batch_size = 500
                for _ in range(batch_size):
                    if self.stop_event.is_set() or self.block_found.is_set():
                        break

                    with self.lock:
                        if self.current_height != height:
                            break

                    # Выполняем PoW
                    mix, new_nseed, mods = memhard_sync(sp, seed, nonce, nseed, buffer_size)

                    with self.lock:
                        self.total_hashes += 1

                    if mods != EXPECTED_MODS:
                        nonce = (nonce + 1) & 0xFFFFFFFFFFFF
                        if nonce > 2 ** 50:
                            nonce = secrets.randbits(48)
                            nseed = secrets.randbits(32)
                        continue

                    # Вычисляем proof
                    proof = hashlib.sha256(
                        f"{mix}{prev_hash}{new_nseed}{mods}".encode()
                    ).hexdigest()

                    proof_int = int(proof, 16)

                    # Для пула
                    if self.pool_mode and proof_int <= pool_target:
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

                    # Для соло
                    elif not self.pool_mode and proof_int <= target:
                        if self.block_found.is_set():
                            break

                        self.block_found.set()

                        with self.lock:
                            current_height = self.current_height
                            current_prev_hash = self.current_prev_hash
                            current_target = self.current_target
                            current_reward = self.current_reward
                            current_transactions = list(self.current_transactions)

                        log.info(f"\n{BO}{YE}╔══════════════════════════════════════════════╗{NC}")
                        log.info(f"{BO}{YE}║   🎯 CANDIDATE BLOCK #{current_height}{NC}")
                        log.info(f"{BO}{YE}╚══════════════════════════════════════════════╝{NC}")

                        # Формируем блок
                        block = {
                            "index": current_height,
                            "previous_hash": current_prev_hash,
                            "transactions": current_transactions[:200],
                            "timestamp": int(time.time()),
                            "nonce": int(nonce),
                            "nonce_seed": int(nseed),  # исходный nseed
                            "memory_proof": proof,
                            "target": current_target,
                            "extra_nonce": thread_id,
                            "miner_payout_address": self.address,
                            "scratchpad_mods": mods,
                            "scratchpad_size": buffer_size,
                            "pool_block": False,
                            "threads_used": self.num_threads,  # <= MAX_THREADS_PER_MINER
                            "version": PROTOCOL
                        }

                        # Локальная проверка
                        log.info(f"\n{BO}{CY}🔍 LOCAL POW VERIFICATION:{NC}")
                        is_valid = verify_pow_sync(block, current_target)
                        log.info(f"  Result: {GR if is_valid else RE}{is_valid}{NC}")

                        if not is_valid:
                            log.error(f"{RE}❌ LOCAL VERIFICATION FAILED!{NC}")
                            self.block_found.clear()
                            with self.lock:
                                self.blocks_rejected += 1
                            nonce = (nonce + 1) & 0xFFFFFFFFFFFF
                            continue

                        log.info(f"{GR}✅ Local verification passed! Signing...{NC}")

                        # Подписываем
                        signature = sign_block(block, self.private_key)
                        if not signature:
                            log.error(f"{RE}❌ Failed to sign block{NC}")
                            self.block_found.clear()
                            nonce = (nonce + 1) & 0xFFFFFFFFFFFF
                            continue

                        block["miner_signature"] = signature

                        # Отправляем
                        log.info(f"{CY}📤 Sending to node...{NC}")
                        resp = http_post("/mine", block, timeout=60)

                        if resp:
                            status = resp.get("status", "unknown")
                            if status == "ok":
                                with self.lock:
                                    self.blocks_mined += 1
                                    self.total_reward += current_reward
                                log.info(f"\n{BO}{GR}╔══════════════════════════════════════════════╗{NC}")
                                log.info(
                                    f"{BO}{GR}║   🎉 BLOCK #{current_height} ACCEPTED! +{current_reward:.2f} RAM{NC}")
                                log.info(f"{BO}{GR}╚══════════════════════════════════════════════╝{NC}")
                            else:
                                with self.lock:
                                    self.blocks_rejected += 1
                                reason = resp.get("reason", "unknown")
                                log.warning(f"\n{BO}{RE}╔══════════════════════════════════════════════╗{NC}")
                                log.warning(f"{BO}{RE}║   ❌ BLOCK #{current_height} REJECTED: {reason}{NC}")
                                log.warning(f"{BO}{RE}╚══════════════════════════════════════════════╝{NC}")

                                # Детальная диагностика
                                log.info(f"\n{CY}🔍 DIAGNOSTICS:{NC}")
                                log.info(f"  Nonce: {block['nonce']}")
                                log.info(f"  Nonce_seed: {block['nonce_seed']}")
                                log.info(f"  Extra_nonce: {block['extra_nonce']}")
                                log.info(f"  Mods: {block['scratchpad_mods']}")
                                log.info(f"  Scratchpad_size: {block['scratchpad_size']}")
                                log.info(f"  Threads_used: {block['threads_used']}")
                                log.info(f"  Proof: {block['memory_proof'][:40]}...")
                                log.info(f"  Full response: {json.dumps(resp, indent=2)}")
                        else:
                            with self.lock:
                                self.blocks_rejected += 1
                            log.error(f"{RE}❌ No response from node{NC}")

                        time.sleep(2)
                        self.block_found.clear()
                        nseed = secrets.randbits(32)
                        nonce = (nonce + 1) & 0xFFFFFFFFFFFF
                        break

                    nonce = (nonce + 1) & 0xFFFFFFFFFFFF
                    if nonce > 2 ** 50:
                        nonce = secrets.randbits(48)
                        nseed = secrets.randbits(32)

            except Exception as e:
                log.error(f"Thread {thread_id} error: {e}")
                log.debug(traceback.format_exc())
                time.sleep(1)
                nonce = secrets.randbits(48)
                nseed = secrets.randbits(32)

    def poller(self) -> None:
        while not self.stop_event.is_set():
            self.update_block_info()
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
                mined = self.blocks_mined
                rejected = self.blocks_rejected
                height = self.current_height
                reward = self.current_reward
                target = self.current_target
                shares = self.pool_shares

            dt = now - last_time
            dh = current_hashes - last_hashes
            speed = dh / dt if dt > 0 else 0

            last_hashes = current_hashes
            last_time = now

            if speed >= 1_000_000:
                speed_str = f"{speed / 1_000_000:.2f} MH/s"
            elif speed >= 1_000:
                speed_str = f"{speed / 1_000:.2f} KH/s"
            else:
                speed_str = f"{speed:.0f} H/s"

            diff = MAX_TARGET / target if target > 0 else 0
            diff_str = f"{diff / 1e6:.1f}M" if diff >= 1e6 else (
                f"{diff / 1e3:.1f}K" if diff >= 1e3 else f"{diff:.0f}")

            daily = (speed / target) * reward * 86400 if target > 0 else 0

            uptime = int(time.time() - self.start_time)
            hh, mm, ss = uptime // 3600, (uptime % 3600) // 60, uptime % 60

            node_str = f"{GR}OK{NC}" if self.node_ok else f"{RE}DOWN{NC}"
            mode = f"{CY}POOL{NC}" if self.pool_mode else f"{GR}SOLO{NC}"

            log.info(
                f"[{hh:02d}:{mm:02d}:{ss:02d}] {mode} {BO}{speed_str}{NC} | "
                f"Block:{CY}#{height}{NC} | "
                f"OK:{GR}{mined}{NC}/Fail:{RE}{rejected}{NC} | "
                f"Diff:{diff_str} | "
                f"Daily:{daily:.4f} RAM | "
                f"Node:{node_str}"
                + (f" | Shares:{shares}" if self.pool_mode else "")
            )

    def run(self) -> None:
        log.info(f"{BO}╔══════════════════════════════════════════════╗{NC}")
        log.info(f"{BO}║   RAMCOIN MINER v{VERSION}{NC}")
        log.info(f"{BO}╚══════════════════════════════════════════════╝{NC}")

        log.info("Syncing...")
        if not self.update_block_info():
            log.error(f"{RE}Failed to sync with node!{NC}")
            sys.exit(1)

        diff = MAX_TARGET / self.current_target if self.current_target > 0 else 0
        diff_str = f"{diff / 1e6:.1f}M" if diff >= 1e6 else (
            f"{diff / 1e3:.1f}K" if diff >= 1e3 else f"{diff:.0f}")

        log.info(f"Ready! Block #{self.current_height} | Diff: {diff_str} | "
                 f"Reward: {self.current_reward} RAM")
        log.info(f"Using {self.num_threads} threads (MAX_THREADS_PER_MINER = {MAX_THREADS_PER_MINER})")
        log.info(f"{GR}{BO}🚀 MINING STARTED!{NC}")

        threading.Thread(target=self.poller, daemon=True).start()
        threading.Thread(target=self.logger, daemon=True).start()

        for tid in range(self.num_threads):
            threading.Thread(target=self.mine_block, args=(tid,), daemon=True).start()

        log.info(f"{GR}{self.num_threads} mining threads started{NC}")

        def stop_handler(sig, frame):
            log.info(f"{YE}Stopping...{NC}")
            self.stop_event.set()
            self.block_found.set()
            time.sleep(2)

            elapsed = time.time() - self.start_time
            log.info(f"\n{BO}══════════════════════════════════════════════{NC}")
            log.info(f"{BO}📊 MINING SUMMARY{NC}")
            log.info(f"{BO}══════════════════════════════════════════════{NC}")
            log.info(f"  Runtime:     {elapsed:.0f}s")
            log.info(f"  Blocks OK:   {GR}{self.blocks_mined}{NC}")
            log.info(f"  Blocks FAIL: {RE}{self.blocks_rejected}{NC}")
            log.info(f"  Total RAM:   {GR}{self.total_reward:.4f}{NC}")
            log.info(f"  Total hashes: {self.total_hashes:,}")
            if elapsed > 0:
                log.info(f"  Avg speed:   {self.total_hashes / elapsed:.0f} H/s")
            log.info(f"{BO}══════════════════════════════════════════════{NC}")
            sys.exit(0)

        signal.signal(signal.SIGINT, stop_handler)
        signal.signal(signal.SIGTERM, stop_handler)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_handler(None, None)


# ==================== MAIN ====================
def main():
    if not os.path.exists(API_KEY_FILE):
        log.error(f"{RE}api_key.txt not found!{NC}")
        sys.exit(1)

    api_key = open(API_KEY_FILE).read().strip()
    if not api_key:
        log.error(f"{RE}Empty API key!{NC}")
        sys.exit(1)

    health = http_get("/health", timeout=3)
    if not health or not health.get("ok"):
        log.error(f"{RE}Node offline!{NC}")
        sys.exit(1)

    log.info(f"Node: v{health.get('version', '?')} H:#{health.get('height', '?')}")

    # Используем максимум 4 потока
    threads = min(os.cpu_count() or 4, MAX_THREADS_PER_MINER)
    log.info(f"Using {threads} threads (MAX_THREADS_PER_MINER = {MAX_THREADS_PER_MINER})\n")

    print(f"1. {GR}SOLO (full reward){NC}")
    print(f"2. {CY}POOL (stable shares){NC}")
    choice = input("Choose [1/2]: ").strip()
    pool_mode = (choice == "2")

    address = input("RAM_ address: ").strip()
    if not address.startswith("RAM_"):
        log.error(f"{RE}Invalid address!{NC}")
        sys.exit(1)

    private_key = None
    if not pool_mode:
        private_key = input("Private key (64 hex): ").strip()
        if len(private_key) != 64:
            log.error(f"{RE}Invalid key! Must be 64 hex characters{NC}")
            sys.exit(1)

    miner = RamcoinMiner(address, private_key, pool_mode, threads)
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