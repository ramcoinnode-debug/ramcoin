#!/usr/bin/env python3
"""
RAMCOIN NODE v10.2.0 - ULTRA SECURE VIRAL P2P NETWORK
Полностью децентрализованная сеть с многоуровневой защитой
Криптографическое доказательство владения IP с обратным вызовом
Градуированная репутационная система для seed-нод
Квантово-устойчивое резервирование
Обнаружение сетевых аномалий
Шифрование P2P-каналов (ChaCha20-Poly1305 + ECDH)
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
import zlib
import hmac
import socket
import ipaddress
import base64
import ssl
import signal
from typing import Optional, Dict, List, Tuple, Set, Any
from collections import defaultdict, deque, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum, auto
import sys
import aiohttp
from aiohttp import web
import lz4.frame
from cryptography.hazmat.primitives.asymmetric import ec, x25519
from cryptography.hazmat.primitives import hashes, serialization, padding
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.exceptions import InvalidSignature
import threading
from prometheus_client import Counter, Gauge, Histogram, start_http_server
import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
# ==================== КОНСТАНТЫ ====================
VERSION = "10.2.0"
PROTOCOL = 2
COIN = 100_000_000
MY_WHITE_IP = "90.188.115.169"

# Адреса
DEV_ADDR = "RAM_04a9b30816a61686f377f152435f528e542b61eb7f0c9403778fdd19862600eb18a4faffe64d6a88a8077da4bf5bf908b74f2729c7fe044ddf5528521f5dcbd75a"
BURN_ADDR = "RAM_BURN_" + "0" * 124

# Базы данных
DB_PATH = "blockchain_v7.db"
PEERS_DB = "peers_v9.db"
ORPHANS_DB = "orphans_v2.db"
SEEDS_DB = "seeds_v11.db"
METRICS_DB = "metrics_v1.db"

# Порты
P2P_PORT = 8333
API_PORT = 5000
METRICS_PORT = 9090
SSL_P2P_PORT = 8334

# Параметры блокчейна
INITIAL_REWARD = 10 * COIN
BLOCK_TIME = 30.0
HALVING = 876_000
MAX_TARGET = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
INITIAL_TARGET = MAX_TARGET >> 4
MIN_TARGET = MAX_TARGET >> 20
MAX_TIME_DRIFT = 7200
MIN_BLOCK_GAP = 5

# Параметры майнинга
SCRATCHPAD_ITER = 8192
BASE_SCRATCHPAD = 524288
MAX_SCRATCHPAD = 4194304
# 🎯 ЧЕСТНЫЙ МАЙНИНГ
MAX_THREADS = 4
SCRATCHPAD_SIZE = 8388608
# Комиссии
FIXED_FEE = int(0.001 * COIN)
DEV_SHARE = 10
POOL_FEE = 0.01
BURN_FEE = 0.01
POOL_DIFF_FACTOR = 100

# Сеть
MAX_PEERS = 500
PEER_TIMEOUT = 300
MAX_MEMPOOL = 10000
MAX_BLOCK_TX = 200

# Безопасность
ANNOUNCE_INTERVAL = 600
MAX_SEED_NODES = 50
SEED_RETENTION = 86400
SEED_PROOF_DIFFICULTY = 1000
MIN_SEED_CONFIRMATIONS = 3
MAX_SEEDS_PER_IP_RANGE = 3
GOSSIP_CACHE_TTL = 3600
MAX_RELAY_COUNT = 10
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 30

# Bootstrap
BOOTSTRAP_SEEDS = [
    "seed1.ramcoin.network:8333",
    "seed2.ramcoin.network:8333",
    "seed3.ramcoin.network:8333",
]

CPU_WORKERS = min(8, (os.cpu_count() or 2))
executor = ThreadPoolExecutor(max_workers=CPU_WORKERS)

# ==================== PROMETHEUS МЕТРИКИ ====================
PEERS_GAUGE = Gauge('ramcoin_peers', 'Number of connected peers')
SEEDS_GAUGE = Gauge('ramcoin_seeds', 'Number of seed nodes')
HEIGHT_GAUGE = Gauge('ramcoin_height', 'Current blockchain height')
MEMPOOL_SIZE = Gauge('ramcoin_mempool_size', 'Mempool size')
BLOCK_TIME_HISTOGRAM = Histogram('ramcoin_block_time_seconds', 'Block time')
TX_COUNTER = Counter('ramcoin_transactions_total', 'Total transactions')
BLOCKS_COUNTER = Counter('ramcoin_blocks_total', 'Total blocks mined')
REPUTATION_GAUGE = Gauge('ramcoin_average_reputation', 'Average seed reputation')

# ==================== ЛОГГИРОВАНИЕ ====================
import sys

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S'))

file_handler = logging.FileHandler('ramcoin.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S'))

logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
log = logging.getLogger('RAMCOIN')


# ==================== ENUMS ====================
class OffenseType(Enum):
    SPAM = auto()
    INVALID_BLOCK = auto()
    DOUBLE_SPEND = auto()
    SYBIL_ATTEMPT = auto()
    ECLIPSE_ATTEMPT = auto()
    PROTOCOL_VIOLATION = auto()
    INVALID_PROOF = auto()


class NetworkHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ==================== DATA CLASSES ====================
@dataclass
class PeerInfo:
    addr: str
    ip: str
    port: int
    last_seen: float = 0
    height: int = 0
    is_white: bool = False
    version: str = ""
    reputation: float = 0
    confirmations: int = 0
    first_seen: float = 0
    connected: bool = False


@dataclass
class SeedProof:
    challenge: str
    response: str
    timestamp: float
    ip: str
    port: int
    verified: bool = False


@dataclass
class NetworkMetrics:
    peers_online: int = 0
    seeds_reachable: int = 0
    block_propagation_time: float = 0
    partition_risk: float = 0
    eclipse_risk: float = 0
    health_score: float = 1.0
    status: NetworkHealth = NetworkHealth.UNKNOWN


# ==================== КРИПТОГРАФИЯ ====================
class CryptoUtils:
    """Расширенные криптографические утилиты с постквантовой подготовкой"""

    @staticmethod
    def generate_ephemeral_keypair():
        """Генерирует ephemeral ключи для ECDH"""
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()
        return private_key, public_key

    @staticmethod
    def derive_shared_key(private_key, peer_public_bytes: bytes) -> bytes:
        """Вычисляет shared secret через ECDH с множественной деривацией"""
        peer_public = x25519.X25519PublicKey.from_public_bytes(peer_public_bytes)
        shared_key = private_key.exchange(peer_public)

        # Множественная деривация для разных целей
        encryption_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"RAMCOIN_P2P_ENCRYPTION_V2",
        ).derive(shared_key)

        return encryption_key

    @staticmethod
    def encrypt_message(key: bytes, plaintext: bytes) -> bytes:
        """Шифрует сообщение с ChaCha20-Poly1305 и сжатием"""
        # Сжимаем если больше 1KB
        if len(plaintext) > 1024:
            plaintext = lz4.frame.compress(plaintext)
            compressed = True
        else:
            compressed = False

        nonce = secrets.token_bytes(12)
        cipher = ChaCha20Poly1305(key)

        # Добавляем флаг сжатия
        data = struct.pack('?', compressed) + plaintext
        ciphertext = cipher.encrypt(nonce, data, b"RAMCOIN_P2P_V2")

        return nonce + ciphertext

    @staticmethod
    def decrypt_message(key: bytes, encrypted_data: bytes) -> bytes:
        """Расшифровывает сообщение"""
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        cipher = ChaCha20Poly1305(key)

        decrypted = cipher.decrypt(nonce, ciphertext, b"RAMCOIN_P2P_V2")

        # Проверяем флаг сжатия
        compressed = struct.unpack('?', decrypted[:1])[0]
        data = decrypted[1:]

        if compressed:
            data = lz4.frame.decompress(data)

        return data

    @staticmethod
    def sign_data(private_key, data: bytes) -> bytes:
        """Подписывает данные ECDSA"""
        signature = private_key.sign(data, ec.ECDSA(hashes.SHA256()))
        return signature

    @staticmethod
    def verify_signature(public_key, signature: bytes, data: bytes) -> bool:
        """Проверяет подпись ECDSA"""
        try:
            public_key.verify(signature, data, ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            return False

    @staticmethod
    def hybrid_encrypt(data: bytes, classical_key, quantum_key=None) -> bytes:
        """Гибридное шифрование с постквантовой подготовкой"""
        # Генерируем симметричный ключ
        symmetric_key = secrets.token_bytes(32)

        # Классическое шифрование симметричного ключа
        encrypted_key_classical = CryptoUtils.encrypt_message(classical_key, symmetric_key)

        # Место для постквантового шифрования
        encrypted_key_quantum = b''
        if quantum_key:
            # Здесь будет постквантовое шифрование
            pass

        # Шифруем данные симметричным ключом
        nonce = secrets.token_bytes(12)
        cipher = ChaCha20Poly1305(symmetric_key)
        ciphertext = cipher.encrypt(nonce, data, b"HYBRID_V1")

        return json.dumps({
            "encrypted_key_classical": encrypted_key_classical.hex(),
            "encrypted_key_quantum": encrypted_key_quantum.hex() if encrypted_key_quantum else "",
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex()
        }).encode()

    @staticmethod
    def generate_quantum_resistant_keypair():
        """Генерирует постквантовую пару ключей (placeholder)"""
        # В будущем здесь будет SPHINCS+ или другой постквантовый алгоритм
        return secrets.token_bytes(32), secrets.token_bytes(64)


class IPUtils:
    """Утилиты для работы с IP адресами"""

    @staticmethod
    def is_private_ip(ip: str) -> bool:
        """Проверяет, является ли IP приватным"""
        try:
            addr = ipaddress.ip_address(ip)
            return addr.is_private or addr.is_loopback or addr.is_multicast or addr.is_reserved
        except:
            return True

    @staticmethod
    def is_public_ip(ip: str) -> bool:
        """Проверяет, является ли IP публичным"""
        return not IPUtils.is_private_ip(ip)

    @staticmethod
    def get_ip_range(ip: str, prefix: int = None) -> str:
        """Возвращает подсеть для IP"""
        try:
            addr = ipaddress.ip_address(ip)
            if isinstance(addr, ipaddress.IPv4Address):
                prefix = prefix or 24
                network = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
            else:
                prefix = prefix or 64
                network = ipaddress.IPv6Network(f"{ip}/{prefix}", strict=False)
            return str(network.network_address)
        except:
            return ip

    @staticmethod
    def is_same_subnet(ip1: str, ip2: str, prefix: int = 24) -> bool:
        """Проверяет, в одной ли подсети два IP"""
        try:
            return IPUtils.get_ip_range(ip1, prefix) == IPUtils.get_ip_range(ip2, prefix)
        except:
            return False

    @staticmethod
    async def verify_remote_ownership(ip: str, port: int, challenge: str, timeout: int = 5) -> bool:
        """Проверяет владение IP через обратное подключение"""
        try:
            # Подключаемся обратно к ноде
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=timeout
            )

            # Отправляем challenge в специальном формате
            verify_msg = json.dumps({
                "type": "ip_verify",
                "challenge": challenge,
                "timestamp": int(time.time())
            }).encode()

            writer.write(struct.pack('>I', len(verify_msg)))
            writer.write(verify_msg)
            await writer.drain()

            # Получаем ответ
            length_data = await asyncio.wait_for(reader.read(4), timeout=timeout)
            if not length_data:
                return False

            length = struct.unpack('>I', length_data)[0]
            if length > 1024:
                return False

            response_data = await asyncio.wait_for(reader.read(length), timeout=timeout)
            response = json.loads(response_data.decode())

            writer.close()

            # Проверяем ответ
            expected_response = hashlib.sha256(
                f"{challenge}:{ip}:{port}:RAMCOIN_VERIFY".encode()
            ).hexdigest()

            return hmac.compare_digest(expected_response, response.get("proof", ""))

        except Exception as e:
            log.debug(f"IP verification failed for {ip}:{port} - {e}")
            return False


class RateLimiter:
    """Улучшенный rate limiter с адаптивными лимитами"""

    def __init__(self):
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.banned: Dict[str, float] = {}
        self.penalties: Dict[str, int] = defaultdict(int)
        self.lock = threading.Lock()
        self.dynamic_limits: Dict[str, int] = {}

    def check(self, key: str, limit: int = RATE_LIMIT_MAX_REQUESTS,
              window: int = RATE_LIMIT_WINDOW) -> bool:
        """Проверяет rate limit с адаптивными ограничениями"""
        now = time.time()

        with self.lock:
            # Проверка бана
            if key in self.banned:
                if now < self.banned[key]:
                    return False
                del self.banned[key]

            # Адаптивный лимит на основе истории нарушений
            adjusted_limit = self.dynamic_limits.get(key, limit)
            adjusted_limit = max(1, adjusted_limit - self.penalties.get(key, 0))

            # Очистка старых запросов
            self.requests[key] = [t for t in self.requests[key] if now - t < window]

            # Проверка лимита
            if len(self.requests[key]) >= adjusted_limit:
                ban_duration = window * (2 ** self.penalties.get(key, 0))
                self.banned[key] = now + ban_duration
                self.penalties[key] += 1
                log.warning(f"🚫 Rate limit exceeded: {key} (penalty: {self.penalties[key]})")
                return False

            self.requests[key].append(now)
            return True

    def reset_penalty(self, key: str):
        """Сбрасывает штрафы для ключа"""
        with self.lock:
            self.penalties[key] = 0
            self.dynamic_limits.pop(key, None)

    def cleanup(self):
        """Очистка устаревших данных с оптимизацией памяти"""
        now = time.time()
        with self.lock:
            # Очистка старых запросов
            for key in list(self.requests.keys()):
                self.requests[key] = [t for t in self.requests[key] if now - t < RATE_LIMIT_WINDOW]
                if not self.requests[key]:
                    del self.requests[key]

            # Очистка истекших банов
            for key in list(self.banned.keys()):
                if now >= self.banned[key]:
                    del self.banned[key]

            # Сброс старых штрафов
            for key in list(self.penalties.keys()):
                if now - max(self.requests.get(key, [0])) > 3600:
                    del self.penalties[key]


# ==================== ЗАЩИЩЕННЫЙ SEED-РЕГИСТР ====================
class SeedRegistry:
    """Расширенный реестр seed-нод с градуированной репутацией"""

    def __init__(self):
        self.seeds: Dict[str, PeerInfo] = {}
        self.reputation: Dict[str, float] = defaultdict(float)
        self.seed_proofs: Dict[str, List[SeedProof]] = defaultdict(list)
        self.confirmations: Dict[str, Set[str]] = defaultdict(set)
        self.ip_ranges: Dict[str, int] = defaultdict(int)
        self.lock = asyncio.Lock()
        self.rate_limiter = RateLimiter()
        self.offense_history: Dict[str, List[Tuple[float, OffenseType]]] = defaultdict(list)
        self._init_db()
        self._load_from_db()

    def _init_db(self):
        """Инициализация БД seed-нод с историей нарушений"""
        with sqlite3.connect(SEEDS_DB) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS seeds 
                          (addr TEXT PRIMARY KEY, ip TEXT, port INTEGER, 
                           reputation REAL, last_seen REAL, version TEXT, 
                           first_seen REAL, proofs TEXT, confirmations TEXT,
                           offenses TEXT)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS seed_proofs
                          (addr TEXT, challenge TEXT, response TEXT, 
                           timestamp REAL, verified INTEGER, ip TEXT, port INTEGER)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS offense_history
                          (addr TEXT, offense_type TEXT, timestamp REAL, 
                           details TEXT)''')
            conn.execute('PRAGMA journal_mode=WAL')

    def _load_from_db(self):
        """Загружает seed-ноды из БД"""
        try:
            with sqlite3.connect(SEEDS_DB) as conn:
                rows = conn.execute(
                    "SELECT addr, ip, port, reputation, last_seen, version, "
                    "first_seen, proofs, confirmations, offenses FROM seeds"
                ).fetchall()

                for row in rows:
                    addr, ip, port, rep, last_seen, ver, first_seen, proofs_json, confs_json, offenses_json = row

                    peer_info = PeerInfo(
                        addr=addr, ip=ip, port=port,
                        last_seen=last_seen, version=ver,
                        first_seen=first_seen
                    )
                    self.seeds[addr] = peer_info
                    self.reputation[addr] = rep

                    if proofs_json:
                        proofs_data = json.loads(proofs_json)
                        self.seed_proofs[addr] = [
                            SeedProof(**p) for p in proofs_data
                        ]

                    if confs_json:
                        self.confirmations[addr] = set(json.loads(confs_json))

                    if offenses_json:
                        self.offense_history[addr] = [
                            (t, OffenseType[o]) for t, o in json.loads(offenses_json)
                        ]

                    # Обновляем счетчик подсетей
                    ip_range = IPUtils.get_ip_range(ip)
                    self.ip_ranges[ip_range] += 1

            log.info(f"🔐 Загружено {len(self.seeds)} seed-нод с репутацией")
        except Exception as e:
            log.error(f"Ошибка загрузки seed-нод: {e}")

    async def add_seed(self, ip: str, port: int, height: int, version: str = "",
                       proof: Optional[SeedProof] = None, require_verification: bool = True) -> bool:
        """Добавляет seed-ноду с улучшенными проверками безопасности"""
        async with self.lock:
            if not IPUtils.is_public_ip(ip):
                return False

            addr = f"{ip}:{port}"

            # Rate limiting с адаптивными лимитами
            if not self.rate_limiter.check(f"add_seed:{addr}"):
                return False

            # Проверка на количество seed-нод в подсети
            ip_range = IPUtils.get_ip_range(ip)
            if addr not in self.seeds and self.ip_ranges[ip_range] >= MAX_SEEDS_PER_IP_RANGE:
                log.warning(f"⚠️ Слишком много seed-нод в подсети {ip_range}")
                await self.record_offense(addr, OffenseType.SYBIL_ATTEMPT)
                return False

            now = time.time()

            # Требуем proof для новых нод с обратной верификацией
            if addr not in self.seeds:
                if proof:
                    if require_verification:
                        if not await self.verify_seed_proof_async(ip, port, proof):
                            return False
                    self.seed_proofs[addr] = [proof]
                    self.confirmations[addr] = set()
                    self.reputation[addr] = 1.0
                    self.ip_ranges[ip_range] += 1
                else:
                    # Без proof - минимальная репутация
                    self.reputation[addr] = 0.1
                    self.rate_limiter.check(f"add_seed:{addr}", limit=3, window=3600)

            # Обновление данных
            peer_info = PeerInfo(
                addr=addr, ip=ip, port=port,
                last_seen=now, height=height,
                version=version,
                first_seen=self.seeds.get(addr, PeerInfo(addr, ip, port)).first_seen or now
            )

            if addr in self.seeds:
                # Увеличиваем репутацию за активность
                if now - self.seeds[addr].last_seen > 3600:
                    self.reputation[addr] = min(100.0, self.reputation[addr] + 0.1)

            self.seeds[addr] = peer_info

            # Сохранение в БД
            await self._save_seed(addr)

            # Обновляем метрики
            SEEDS_GAUGE.set(len(self.seeds))

            return True

    async def verify_seed_proof_async(self, ip: str, port: int, proof: SeedProof) -> bool:
        """Асинхронная проверка proof с обратным вызовом"""
        try:
            # Проверка времени (не старше 5 минут)
            if abs(time.time() - proof.timestamp) > 300:
                return False

            # Проверка proof-of-work
            expected = hashlib.sha256(
                f"{proof.challenge}:{ip}:{port}:RAMCOIN_SEED_PROOF_V2".encode()
            ).hexdigest()

            # Проверяем сложность
            if int(expected, 16) > (MAX_TARGET // SEED_PROOF_DIFFICULTY):
                return False

            # Криптографическая проверка
            basic_valid = hmac.compare_digest(expected, proof.response)

            if not basic_valid:
                return False

            # Обратная верификация (опционально)
            if proof.challenge and proof.challenge.startswith("verify_"):
                verified = await IPUtils.verify_remote_ownership(
                    ip, port, proof.challenge, timeout=5
                )
                if not verified:
                    await self.record_offense(f"{ip}:{port}", OffenseType.INVALID_PROOF)
                    return False

            proof.verified = True
            return True

        except Exception as e:
            log.error(f"Ошибка проверки proof: {e}")
            return False

    async def add_confirmation(self, seed_addr: str, confirmer_addr: str) -> bool:
        """Добавляет подтверждение seed-ноды от другой ноды с проверками"""
        async with self.lock:
            if seed_addr not in self.seeds or confirmer_addr not in self.seeds:
                return False

            # Проверяем, не из одной ли подсети
            seed_ip = self.seeds[seed_addr].ip
            confirmer_ip = self.seeds[confirmer_addr].ip

            if IPUtils.is_same_subnet(seed_ip, confirmer_ip):
                # Уменьшаем вес подтверждения из той же подсети
                reputation_gain = 2.0
            else:
                reputation_gain = 5.0

            if confirmer_addr not in self.confirmations[seed_addr]:
                self.confirmations[seed_addr].add(confirmer_addr)
                self.reputation[seed_addr] = min(100.0, self.reputation[seed_addr] + reputation_gain)
                await self._save_seed(seed_addr)

            return True

    def get_active_seeds(self, limit: int = MAX_SEED_NODES,
                         min_reputation: float = 0.0,
                         exclude_subnet: str = None) -> List[PeerInfo]:
        """Возвращает активные seed-ноды с улучшенной фильтрацией"""
        now = time.time()
        active = []

        for addr, info in self.seeds.items():
            if now - info.last_seen < SEED_RETENTION:
                rep = self.reputation.get(addr, 0)
                confs = len(self.confirmations.get(addr, set()))

                # Исключаем подсеть если нужно (для защиты от Eclipse)
                if exclude_subnet and IPUtils.is_same_subnet(
                        info.ip, exclude_subnet
                ):
                    continue

                if rep >= min_reputation and confs >= MIN_SEED_CONFIRMATIONS:
                    active.append(info)

        # Сортировка по репутации и высоте
        active.sort(key=lambda x: (self.reputation.get(x.addr, 0), x.height), reverse=True)

        # Разнообразим по подсетям
        diverse = []
        seen_subnets = set()

        for peer in active:
            subnet = IPUtils.get_ip_range(peer.ip)
            if subnet not in seen_subnets or len(diverse) < limit // 2:
                diverse.append(peer)
                seen_subnets.add(subnet)

            if len(diverse) >= limit:
                break

        return diverse[:limit]

    async def graduated_penalty(self, addr: str, offense: OffenseType):
        """Градуированная система штрафов"""
        penalties = {
            OffenseType.SPAM: 0.5,
            OffenseType.INVALID_BLOCK: 2.0,
            OffenseType.DOUBLE_SPEND: 5.0,
            OffenseType.SYBIL_ATTEMPT: 10.0,
            OffenseType.ECLIPSE_ATTEMPT: 20.0,
            OffenseType.PROTOCOL_VIOLATION: 3.0,
            OffenseType.INVALID_PROOF: 4.0
        }

        penalty = penalties.get(offense, 1.0)

        async with self.lock:
            await self.record_offense(addr, offense)
            self.reputation[addr] -= penalty

            rep = self.reputation[addr]
            log.info(f"⚖️ Штраф для {addr}: {penalty} ({offense.name}), репутация: {rep:.1f}")

            if rep < -20:
                await self._permanent_ban(addr)
                log.critical(f"🚫 Перманентный бан: {addr}")
            elif rep < -10:
                await self._isolate_peer(addr, hours=24)
                log.warning(f"🔒 Изоляция на 24ч: {addr}")
            elif rep < -5:
                await self._temporary_ban(addr, hours=1)
                log.info(f"⏰ Временный бан на 1ч: {addr}")

    async def record_offense(self, addr: str, offense: OffenseType):
        """Записывает нарушение в историю"""
        self.offense_history[addr].append((time.time(), offense))

        # Храним только последние 100 нарушений
        if len(self.offense_history[addr]) > 100:
            self.offense_history[addr] = self.offense_history[addr][-100:]

        # Сохраняем в БД
        try:
            with sqlite3.connect(SEEDS_DB, timeout=10) as conn:
                conn.execute(
                    "INSERT INTO offense_history VALUES (?,?,?,?)",
                    (addr, offense.name, time.time(), "")
                )
        except:
            pass

    async def _permanent_ban(self, addr: str):
        """Перманентный бан ноды"""
        async with self.lock:
            await self.remove_seed(addr)
            # Добавляем в черный список
            self.rate_limiter.banned[addr] = time.time() + 365 * 86400  # 1 год

    async def _isolate_peer(self, addr: str, hours: int):
        """Изолирует пира на указанное время"""
        self.rate_limiter.banned[addr] = time.time() + hours * 3600

    async def _temporary_ban(self, addr: str, hours: int):
        """Временный бан"""
        self.rate_limiter.banned[addr] = time.time() + hours * 3600

    async def decrease_reputation(self, addr: str, penalty: float = 1.0):
        """Уменьшает репутацию ноды"""
        async with self.lock:
            self.reputation[addr] = max(-100.0, self.reputation.get(addr, 0) - penalty)
            if self.reputation[addr] <= -50:
                await self.remove_seed(addr)

    async def remove_seed(self, addr: str):
        """Удаляет seed-ноду"""
        async with self.lock:
            if addr in self.seeds:
                ip_range = IPUtils.get_ip_range(self.seeds[addr].ip)
                self.ip_ranges[ip_range] = max(0, self.ip_ranges[ip_range] - 1)
                del self.seeds[addr]
                self.reputation.pop(addr, None)
                self.seed_proofs.pop(addr, None)
                self.confirmations.pop(addr, None)
                self.offense_history.pop(addr, None)

                try:
                    with sqlite3.connect(SEEDS_DB, timeout=10) as conn:
                        conn.execute("DELETE FROM seeds WHERE addr=?", (addr,))
                        conn.execute("DELETE FROM seed_proofs WHERE addr=?", (addr,))
                        conn.execute("DELETE FROM offense_history WHERE addr=?", (addr,))
                except:
                    pass

                SEEDS_GAUGE.set(len(self.seeds))

    async def _save_seed(self, addr: str):
        """Сохраняет seed-ноду в БД"""
        try:
            if addr not in self.seeds:
                return

            info = self.seeds[addr]
            with sqlite3.connect(SEEDS_DB, timeout=10) as conn:
                proofs_json = json.dumps([
                    {"challenge": p.challenge, "response": p.response,
                     "timestamp": p.timestamp, "verified": p.verified,
                     "ip": p.ip, "port": p.port}
                    for p in self.seed_proofs.get(addr, [])
                ])

                confirmations_json = json.dumps(list(self.confirmations.get(addr, set())))

                offenses_json = json.dumps([
                    (t, o.name) for t, o in self.offense_history.get(addr, [])
                ])

                conn.execute(
                    "INSERT OR REPLACE INTO seeds VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (addr, info.ip, info.port,
                     self.reputation.get(addr, 0),
                     info.last_seen,
                     info.version,
                     info.first_seen,
                     proofs_json,
                     confirmations_json,
                     offenses_json)
                )
        except Exception as e:
            log.error(f"Ошибка сохранения seed: {e}")

    async def cleanup(self):
        """Очистка устаревших и неактивных seed-нод"""
        async with self.lock:
            now = time.time()
            cutoff = now - SEED_RETENTION * 3

            dead = []
            for addr, info in self.seeds.items():
                if now - info.last_seen > cutoff:
                    dead.append(addr)
                elif self.reputation.get(addr, 0) < -10:
                    dead.append(addr)

            for addr in dead:
                await self.remove_seed(addr)

            if dead:
                log.info(f"🧹 Удалено {len(dead)} устаревших seed-нод")

        self.rate_limiter.cleanup()

    def get_stats(self) -> dict:
        """Возвращает статистику seed-нод"""
        active = len([s for s in self.seeds.values()
                      if time.time() - s.last_seen < SEED_RETENTION])
        avg_rep = sum(self.reputation.values()) / max(1, len(self.reputation))

        return {
            "total": len(self.seeds),
            "active": active,
            "average_reputation": avg_rep,
            "unique_subnets": len(self.ip_ranges),
            "confirmed_seeds": len([s for s in self.confirmations
                                    if len(self.confirmations[s]) >= MIN_SEED_CONFIRMATIONS])
        }


# ==================== ДЕТЕКТОР АНОМАЛИЙ ====================
class AnomalyDetector:
    """Обнаружение сетевых аномалий"""

    def __init__(self):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.thresholds = {
            "block_time": BLOCK_TIME,
            "tx_rate": 1000,
            "peer_churn": 0.3,
            "orphan_rate": 0.05,
            "reorg_depth": 3
        }
        self.alerts: List[dict] = []
        self.alert_lock = asyncio.Lock()

    def add_metric(self, name: str, value: float):
        """Добавляет метрику для анализа"""
        self.metrics[name].append((time.time(), value))

    async def check_anomaly(self, metric: str, value: float) -> bool:
        """Проверяет аномалии в метриках"""
        self.add_metric(metric, value)

        if len(self.metrics[metric]) < 10:
            return False

        # Вычисляем статистику
        values = [v for _, v in self.metrics[metric]]
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = variance ** 0.5

        if std == 0:
            return False

        # Z-score для определения аномалий
        z_score = (value - mean) / std

        if abs(z_score) > 3:
            alert = {
                "metric": metric,
                "value": value,
                "mean": mean,
                "std": std,
                "z_score": z_score,
                "timestamp": time.time()
            }

            async with self.alert_lock:
                self.alerts.append(alert)
                if len(self.alerts) > 1000:
                    self.alerts = self.alerts[-1000:]

            log.warning(f"🚨 Аномалия: {metric} = {value:.2f} "
                        f"(μ={mean:.2f}, σ={std:.2f}, z={z_score:.2f})")
            return True

        return False

    def get_recent_alerts(self, minutes: int = 60) -> List[dict]:
        """Возвращает последние алерты"""
        cutoff = time.time() - minutes * 60
        return [a for a in self.alerts if a["timestamp"] > cutoff]


# ==================== МОНИТОР ЗДОРОВЬЯ СЕТИ ====================
class NetworkHealthMonitor:
    """Мониторинг здоровья сети"""

    def __init__(self, p2p_manager):
        self.p2p = p2p_manager
        self.health_history: deque = deque(maxlen=100)
        self.last_check = 0

    async def check_network_health(self) -> NetworkMetrics:
        """Проверяет здоровье сети"""
        metrics = NetworkMetrics()

        # Количество пиров
        metrics.peers_online = len(self.p2p.connections)

        # Достижимость seed-нод
        metrics.seeds_reachable = await self._check_seeds_reachability()

        # Время распространения блока
        metrics.block_propagation = await self._measure_block_propagation()

        # Риск партицирования
        metrics.partition_risk = self._assess_partition_risk()

        # Риск Eclipse-атаки
        metrics.eclipse_risk = self._assess_eclipse_risk()

        # Общий показатель здоровья
        metrics.health_score = self._calculate_health_score(metrics)

        # Определяем статус
        if metrics.health_score > 0.8:
            metrics.status = NetworkHealth.HEALTHY
        elif metrics.health_score > 0.5:
            metrics.status = NetworkHealth.DEGRADED
        else:
            metrics.status = NetworkHealth.CRITICAL

        self.health_history.append(metrics)
        self.last_check = time.time()

        return metrics

    async def _check_seeds_reachability(self) -> int:
        """Проверяет доступность seed-нод"""
        active_seeds = self.p2p.seed_registry.get_active_seeds(20)
        reachable = 0

        # Асинхронно проверяем соединения
        tasks = []
        for seed in active_seeds[:10]:
            task = asyncio.create_task(self._ping_seed(seed.ip, seed.port))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        reachable = sum(1 for r in results if r is True)

        return reachable

    async def _ping_seed(self, ip: str, port: int) -> bool:
        """Пингует seed-ноду"""
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=3
            )
            writer.close()
            return True
        except:
            return False

    async def _measure_block_propagation(self) -> float:
        """Измеряет время распространения блока"""
        # Упрощенная реализация
        return 2.5  # Секунды

    def _assess_partition_risk(self) -> float:
        """Оценивает риск партицирования сети"""
        active_seeds = len(self.p2p.seed_registry.get_active_seeds(100))

        if active_seeds < 10:
            return 0.9
        elif active_seeds < 30:
            return 0.5
        elif active_seeds < 50:
            return 0.2

        return 0.1

    def _assess_eclipse_risk(self) -> float:
        """Оценка риска Eclipse-атаки"""
        subnet_distribution = defaultdict(int)
        total_peers = 0

        for addr in self.p2p.connections:
            ip = addr.split(":")[0]
            subnet = IPUtils.get_ip_range(ip)
            subnet_distribution[subnet] += 1
            total_peers += 1

        if total_peers == 0:
            return 1.0

        # Проверяем концентрацию в подсетях
        max_subnet_ratio = max(subnet_distribution.values()) / total_peers if subnet_distribution else 1.0

        if len(subnet_distribution) < 3:
            return 0.9
        elif max_subnet_ratio > 0.5:
            return 0.7
        elif len(subnet_distribution) < 10:
            return 0.4

        return 0.1

    def _calculate_health_score(self, metrics: NetworkMetrics) -> float:
        """Вычисляет общий показатель здоровья"""
        score = 1.0

        # Штраф за малое количество пиров
        if metrics.peers_online < 10:
            score -= 0.3
        elif metrics.peers_online < 50:
            score -= 0.1

        # Штраф за риски
        score -= metrics.partition_risk * 0.3
        score -= metrics.eclipse_risk * 0.3

        # Штраф за недоступность seed-нод
        if metrics.seeds_reachable < 3:
            score -= 0.2

        return max(0.0, min(1.0, score))


# ==================== PROOF OF WORK ====================
def create_scratchpad_sync(prev_hash, tid, nseed, buffer_size, miner_address="", extra_nonce=0):
    """Создает scratchpad для майнинга"""
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
    """Memory-hard функция для PoW"""
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
    """Синхронная проверка PoW"""
    try:
        buffer_size = int(block.get("scratchpad_size", BASE_SCRATCHPAD))
        if buffer_size < BASE_SCRATCHPAD or buffer_size > MAX_SCRATCHPAD:
            return False
        sp, seed = create_scratchpad_sync(
            str(block["previous_hash"]),
            int(block.get("extra_nonce", 0)),
            int(block.get("nonce_seed", 0)),
            buffer_size,
            block.get("miner_payout_address", ""),
            int(block.get("extra_nonce", 0))
        )
        mix, new_nseed, mods = memhard_sync(
            sp, seed, int(block["nonce"]),
            int(block.get("nonce_seed", 0)), buffer_size
        )
        expected = SCRATCHPAD_ITER + (SCRATCHPAD_ITER // 256) + (SCRATCHPAD_ITER // 50000)
        if mods != expected:
            return False
        proof = hashlib.sha256(f"{mix}{block['previous_hash']}{new_nseed}{mods}".encode()).hexdigest()
        return hmac.compare_digest(proof.encode(), block.get("memory_proof", "").encode()) and int(proof, 16) <= target
    except:
        return False


async def verify_pow_async(block, target):
    """Асинхронная проверка PoW"""
    return await asyncio.get_event_loop().run_in_executor(executor, verify_pow_sync, block, target)


# ==================== БЛОКЧЕЙН ====================
class Blockchain:
    """Блокчейн с расширенной безопасностью"""

    def __init__(self, p2p=None):
        self.p2p = p2p
        self.lock = asyncio.Lock()
        self.share_lock = asyncio.Lock()
        self.fork_lock = asyncio.Lock()
        self.mempool_lock = asyncio.Lock()
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
        self.orphans = {}
        self.anomaly_detector = AnomalyDetector()

        self._init_db()
        if not self._load():
            self._create_genesis()

        log.info(f"✅ RAMCOIN v{VERSION} | H:{self.height} | D:{self.fmt_diff()} | Аккаунтов: {len(self.accounts)}")
        HEIGHT_GAUGE.set(self.height)

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS blocks 
                          (idx INTEGER PRIMARY KEY, data TEXT, hash TEXT UNIQUE)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS state 
                          (key TEXT PRIMARY KEY, val TEXT)''')
            conn.execute('PRAGMA journal_mode=WAL')

    def _load(self):
        try:
            if not os.path.exists(DB_PATH):
                return False
            with sqlite3.connect(DB_PATH) as conn:
                for key in ['height', 'accounts', 'nonces', 'target', 'total_tx', 'accepted', 'rejected']:
                    if not conn.execute("SELECT val FROM state WHERE key=?", (key,)).fetchone():
                        return False

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

                for i in range(1, len(self.chain)):
                    if self.chain[i]["previous_hash"] != self.chain[i - 1]["hash"]:
                        log.error(f"❌ ЦЕПЬ РВАНАЯ на блоке {i}!")
                        return False

                log.info(f"📦 Загружено {self.height} блоков")
                return True
        except Exception as e:
            log.error(f"Ошибка загрузки: {e}")
            return False

    def _create_genesis(self):
        g = {
            "index": 0, "previous_hash": "0" * 64, "transactions": [],
            "timestamp": int(time.time() - BLOCK_TIME),
            "nonce": 0, "nonce_seed": 0, "memory_proof": "0" * 64,
            "target": self.target, "miner_payout_address": DEV_ADDR,
            "miner_signature": "0" * 128, "extra_nonce": 0,
            "scratchpad_mods": 0, "scratchpad_size": BASE_SCRATCHPAD,
            "version": PROTOCOL
        }
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
                for key, val in [
                    ('height', str(self.height)), ('accounts', json.dumps(self.accounts)),
                    ('nonces', json.dumps(self.nonces)), ('target', str(self.target)),
                    ('total_tx', str(self.total_tx)), ('accepted', str(self.accepted)),
                    ('rejected', str(self.rejected))
                ]:
                    conn.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, val))
                conn.commit()
        except Exception as e:
            log.error(f"Ошибка сохранения: {e}")

    def calc_hash(self, block):
        c = block.copy()
        c.pop("hash", None)
        c.pop("miner_signature", None)
        return hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()

    def fmt_diff(self):
        if self.target == 0:
            return "∞"
        sd = MAX_TARGET / self.target
        if sd >= 1e9:
            return f"{sd / 1e9:.2f} GRam/s"
        if sd >= 1e6:
            return f"{sd / 1e6:.2f} MRam/s"
        return f"{sd / 1e3:.2f} KRam/s" if sd >= 1e3 else f"{sd:.2f} Ram/s"

    def _adjust_target(self):
        """Умная сложность — идеал 25-35 секунд"""
        if self.height < 2:
            return

        actual_time = self.chain[-1]["timestamp"] - self.chain[-2]["timestamp"]
        actual_time = max(MIN_BLOCK_GAP, min(actual_time, BLOCK_TIME * 10))

        if actual_time < 10:
            adjustment = 0.65
        elif actual_time < 20:
            adjustment = 0.80
        elif actual_time < 25:
            adjustment = 0.90
        elif actual_time <= 35:
            adjustment = 1.0
        elif actual_time < 50:
            adjustment = 1.10
        elif actual_time < 90:
            adjustment = 1.25
        else:
            adjustment = 1.40

        new_target = int(self.target * adjustment)
        min_target = MAX_TARGET // 1000000
        max_target = MAX_TARGET // 2
        new_target = max(min_target, min(max_target, new_target))
        self.target = new_target

        # Проверяем аномалии во времени блока
        asyncio.create_task(self._check_block_time_anomaly(actual_time))

    async def _check_block_time_anomaly(self, block_time: float):
        """Проверяет аномалии во времени блока"""
        is_anomaly = await self.anomaly_detector.check_anomaly("block_time", block_time)
        if is_anomaly:
            log.warning(f"⚠️ Аномальное время блока: {block_time:.2f}с")

    def reward_at(self, h):
        x = h // HALVING
        return 0 if x >= 64 else INITIAL_REWARD >> x

    def verify_block_signature(self, block: dict) -> bool:
        if block.get("pool_block", False):
            return True
        miner_address = block.get("miner_payout_address", "")
        if not miner_address.startswith("RAM_"):
            return False
        signature_hex = block.get("miner_signature", "")
        if not signature_hex or signature_hex == "0" * 128:
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
        except InvalidSignature:
            return False
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
            signing_data = {
                "sender": tx["sender"], "recipient": tx["recipient"],
                "amount": int(tx["amount"]), "fee": int(tx.get("fee", FIXED_FEE)),
                "nonce": int(tx["nonce"]), "timestamp": int(tx["timestamp"])
            }
            hash_bytes = json.dumps(signing_data, sort_keys=True).encode()
            signature = bytes.fromhex(tx.get("signature", ""))
            pub_key.verify(signature, hash_bytes, ec.ECDSA(hashes.SHA256()))
            return True
        except:
            return False

    async def resolve_fork(self, alt_chain: list) -> bool:
        """Разрешение форков с учетом консенсуса сети"""
        async with self.fork_lock:
            if len(alt_chain) <= len(self.chain):
                return False

            # Валидация альтернативной цепи
            for i in range(1, len(alt_chain)):
                if alt_chain[i]["previous_hash"] != alt_chain[i - 1]["hash"]:
                    return False
                if not verify_pow_sync(alt_chain[i], alt_chain[i].get("target", self.target)):
                    return False

            fork_point = 0
            for i in range(min(len(self.chain), len(alt_chain))):
                if self.chain[i]["hash"] != alt_chain[i]["hash"]:
                    fork_point = i
                    break

            if fork_point == 0:
                return False

            log.warning(f"🔀 ФОРК на блоке #{fork_point}")

            # Сохраняем состояние
            saved_chain = self.chain[:fork_point]
            saved_accounts = self.accounts.copy()
            saved_nonces = self.nonces.copy()
            saved_target = self.target
            saved_total_tx = self.total_tx

            # Применяем форк
            self.chain = saved_chain
            self.height = fork_point
            self._rebuild_state()

            for block in alt_chain[fork_point:]:
                success, msg = await self.add_block(block, "fork")
                if not success:
                    log.error(f"❌ Форк отклонён: {msg}")
                    # Восстанавливаем состояние
                    self.chain = saved_chain + self.chain[fork_point:]
                    self.accounts = saved_accounts
                    self.nonces = saved_nonces
                    self.target = saved_target
                    self.total_tx = saved_total_tx
                    self.height = len(self.chain)
                    return False

            log.info(f"✅ Форк разрешён. H:{self.height}")

            # Проверяем аномалию реорганизации
            await self.anomaly_detector.check_anomaly("reorg_depth", len(alt_chain) - fork_point)

            return True

    def _rebuild_state(self):
        self.accounts = {DEV_ADDR: 100 * COIN}
        self.nonces = {DEV_ADDR: 0}
        self.total_tx = 0
        for block in self.chain:
            if block["index"] == 0:
                continue
            miner = block.get("miner_payout_address", "")
            is_pool = block.get("pool_block", False)
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

            if idx > self.height:
                log.info(f"👻 Орфанный блок #{idx} (мы на {self.height})")
                # Сохраняем орфанный блок
                self.orphans[block.get("hash", "")] = block
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

            # 🛡️ ПРОВЕРКА ЧЕСТНОСТИ МАЙНИНГА
            threads_used = block.get("threads_used", 1)
            ram_used = block.get("scratchpad_size", BASE_SCRATCHPAD)

            if threads_used > MAX_THREADS:
                self.rejected += 1
                log.warning(f"🚫 ЧИТЕР: {threads_used} потоков (макс {MAX_THREADS})")
                return False, "cheater_threads"

            if ram_used > SCRATCHPAD_SIZE:
                self.rejected += 1
                log.warning(f"🚫 ЧИТЕР: {ram_used // 1024 // 1024}MB RAM (макс {SCRATCHPAD_SIZE // 1024 // 1024}MB)")
                return False, "cheater_ram"

            log.info(f"✅ Честный майнинг: {threads_used} потока × {ram_used // 1024 // 1024}MB RAM")

            miner = block.get("miner_payout_address", "")
            is_pool = block.get("pool_block", False)
            reward = 0


            validated_txs = []
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
                df = (fee * DEV_SHARE) // 100
                mf = fee - df
                self.accounts[s] = self.accounts.get(s, 0) - (a + fee)
                self.accounts[DEV_ADDR] = self.accounts.get(DEV_ADDR, 0) + df
                self.accounts[miner] = self.accounts.get(miner, 0) + mf
                self.accounts[r] = self.accounts.get(r, 0) + a
                self.nonces[s] = expected_nonce + 1
                self.total_tx += 1

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
                            if p > 0:
                                self.accounts[a] = self.accounts.get(a, 0) + p
                    self.pool_shares.clear()
                    self.pool_total = 0
            else:
                reward = self.reward_at(idx)
                self.accounts[miner] = self.accounts.get(miner, 0) + reward

            # Обновляем mempool
            async with self.mempool_lock:
                tx_hashes_in_block = {tx.get("signature") for tx in validated_txs}
                self.mempool_hashes -= tx_hashes_in_block
                new_mempool = deque(maxlen=MAX_MEMPOOL)
                for tx in self.mempool:
                    if tx.get("signature") not in tx_hashes_in_block:
                        new_mempool.append(tx)
                self.mempool = new_mempool

            self._adjust_target()
            block["target"] = self.target
            block["hash"] = self.calc_hash(block)
            self._save_block(block)
            self.chain.append(block)
            self.height += 1
            self.last_block_time = block["timestamp"]
            self.accepted += 1

            # Обновляем метрики
            HEIGHT_GAUGE.set(self.height)
            BLOCKS_COUNTER.inc()
            TX_COUNTER.inc(len(validated_txs))
            MEMPOOL_SIZE.set(len(self.mempool))
            BLOCK_TIME_HISTOGRAM.observe(time.time() - self.last_block_time)

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
                block = {
                    "index": self.height, "previous_hash": prev_hash,
                    "timestamp": int(time.time()), "nonce": nonce,
                    "nonce_seed": nseed, "memory_proof": proof,
                    "target": self.target, "extra_nonce": extra,
                    "miner_payout_address": addr, "scratchpad_mods": mods,
                    "scratchpad_size": size, "pool_block": True,
                    "transactions": list(self.mempool)[:MAX_BLOCK_TX],
                    "version": PROTOCOL, "miner_signature": "",
                    "threads_used": MAX_THREADS  # 🔥 ДОБАВИТЬ
                }
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
        self.pool_template = {
            "height": self.height,
            "previous_hash": self.chain[-1]["hash"],
            "target": self.target,
            "pool_target": min(MAX_TARGET, int(self.target * POOL_DIFF_FACTOR)),
            "transactions": list(self.mempool)[:100],
            "timestamp": int(now)
        }
        self.pool_template_ts = now
        return self.pool_template

    async def _notify(self, block):
        msg = json.dumps({
            "event": "new_block",
            "height": self.height,
            "hash": block["hash"],
            "target": self.target
        })
        dead = set()
        for ws in list(self.ws_clients):
            try:
                if not ws.closed:
                    await ws.send_str(msg)
            except:
                dead.add(ws)
        self.ws_clients -= dead

    def get_stats(self):
        return {
            "version": VERSION,
            "height": self.height,
            "difficulty": self.fmt_diff(),
            "total_supply": sum(self.accounts.values()) / COIN,
            "accounts": len(self.accounts),
            "peers": len(self.p2p.connections) if self.p2p else 0,
            "miners": len(self.ws_clients),
            "mempool": len(self.mempool),
            "transactions": self.total_tx,
            "blocks": self.accepted,
            "uptime": int(time.time() - self.start_time),
            "reward": self.reward_at(self.height) / COIN,
            "pool": {"shares": self.pool_total, "miners": len(self.pool_shares)},
            "burn": self.accounts.get(BURN_ADDR, 0) / COIN,
            "current_target": self.target,
            "chain": self.chain[-10:],
            "length": self.height
        }

    def get_address(self, addr):
        if not addr.startswith("RAM_"):
            return None
        return {
            "address": addr,
            "balance": self.accounts.get(addr, 0) / COIN,
            "nonce": self.nonces.get(addr, 0)
        }


# ==================== ЗАЩИЩЕННЫЙ P2P МЕНЕДЖЕР ====================
class SecurePeerManager:
    """Расширенный P2P менеджер с полным набором защит"""

    def __init__(self, bc=None):
        self.bc = bc
        self.peers: Dict[str, PeerInfo] = {}
        self.white_peers: Dict[str, PeerInfo] = {}
        self.grey_peers: Dict[str, PeerInfo] = {}
        self.banned: Dict[str, float] = {}
        self.scores = defaultdict(int)
        self.connections: Dict[str, dict] = {}
        self.server = None
        self.ssl_server = None
        self.running = False
        self.syncing = False
        self.peer_db = PeerDB()
        self.seed_registry = SeedRegistry()
        self.my_ip = MY_WHITE_IP
        self.is_white = IPUtils.is_public_ip(self.my_ip)
        self.rate_limiter = RateLimiter()
        self.gossip_cache: Dict[str, float] = {}
        self.health_monitor = NetworkHealthMonitor(self)
        self.anomaly_detector = AnomalyDetector()

        # Ключи
        self.ephemeral_private_key = None
        self.ephemeral_public_key = None
        self.quantum_private_key = None
        self.quantum_public_key = None
        self._generate_keys()

        # Загружаем пиров
        saved = self.peer_db.load_peers()
        for addr, info in saved.items():
            peer_info = PeerInfo(
                addr=addr,
                ip=info.get("ip", ""),
                port=info.get("port", 0),
                last_seen=info.get("last_seen", 0),
                height=info.get("height", 0),
                is_white=info.get("is_white", False),
                version=info.get("version", "")
            )
            if info.get("is_white", False):
                self.white_peers[addr] = peer_info
            else:
                self.grey_peers[addr] = peer_info
            self.peers[addr] = peer_info

        log.info(f"🔒 Защищенный P2P менеджер v{VERSION}")
        log.info(f"🌐 Пиров: {len(self.white_peers)} белых, {len(self.grey_peers)} серых")
        log.info(f"📍 Мой IP: {self.my_ip} ({'БЕЛЫЙ' if self.is_white else 'СЕРЫЙ'})")

        PEERS_GAUGE.set(len(self.peers))

    def _generate_keys(self):
        """Генерирует все необходимые ключи"""
        self.ephemeral_private_key, self.ephemeral_public_key = CryptoUtils.generate_ephemeral_keypair()
        self.quantum_private_key, self.quantum_public_key = CryptoUtils.generate_quantum_resistant_keypair()
        log.debug("🔑 Все ключи сгенерированы")

    async def start_server(self, host: str, port: int):
        """Запускает P2P сервер с защищенными соединениями"""
        try:
            # Обычный сервер
            self.server = await asyncio.start_server(
                self._handle_secure, host, port
            )

            # SSL сервер (если есть сертификаты)
            if os.path.exists('cert.pem') and os.path.exists('key.pem'):
                ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ssl_context.load_cert_chain('cert.pem', 'key.pem')
                self.ssl_server = await asyncio.start_server(
                    self._handle_secure, host, SSL_P2P_PORT, ssl=ssl_context
                )
                log.info(f"🔐 SSL P2P сервер: {host}:{SSL_P2P_PORT}")

            self.running = True
            log.info(f"🔒 P2P сервер: {host}:{port}")

            # Регистрируем себя как seed-ноду
            if self.is_white and self.bc:
                proof = await self._generate_seed_proof()
                await self.seed_registry.add_seed(
                    self.my_ip, P2P_PORT,
                    self.bc.height, VERSION, proof
                )
                log.info(f"🌟 Зарегистрирован как SEED-нода: {self.my_ip}:{P2P_PORT}")

            # Bootstrap
            await self._bootstrap_from_dns()

            # Подключаемся к seed-нодам
            seeds = self.seed_registry.get_active_seeds(20, min_reputation=1.0)
            for seed in seeds:
                if seed.ip != self.my_ip:
                    asyncio.create_task(self._connect_secure(seed.ip, seed.port))

            # Фоновые задачи
            asyncio.create_task(self._peer_discovery_loop())
            asyncio.create_task(self._announce_loop())
            asyncio.create_task(self._seed_cleanup_loop())
            asyncio.create_task(self._gossip_cleanup_loop())
            asyncio.create_task(self._health_check_loop())
            asyncio.create_task(self._metrics_update_loop())

        except Exception as e:
            log.error(f"Ошибка запуска P2P сервера: {e}")

    async def _bootstrap_from_dns(self):
        """Загружает начальные seed-ноды из DNS"""
        for seed_dns in BOOTSTRAP_SEEDS:
            try:
                ip = seed_dns.split(":")[0]
                port = int(seed_dns.split(":")[1]) if ":" in seed_dns else P2P_PORT
                if ip != self.my_ip:
                    asyncio.create_task(self._connect_secure(ip, port))
            except Exception as e:
                log.debug(f"Не удалось подключиться к bootstrap: {seed_dns}: {e}")

    async def _generate_seed_proof(self) -> SeedProof:
        """Генерирует proof-of-IP для регистрации seed-нодой"""
        challenge = secrets.token_hex(32)
        timestamp = int(time.time())

        # Proof-of-work для доказательства
        proof_hash = hashlib.sha256(
            f"{challenge}:{self.my_ip}:{P2P_PORT}:RAMCOIN_SEED_PROOF_V2".encode()
        ).hexdigest()

        response = hashlib.sha256(
            f"{proof_hash}:{timestamp}:{secrets.token_hex(16)}".encode()
        ).hexdigest()

        return SeedProof(
            challenge=challenge,
            response=response,
            timestamp=timestamp,
            ip=self.my_ip,
            port=P2P_PORT
        )

    async def _handle_secure(self, reader, writer):
        """Обработчик защищенных соединений"""
        peername = writer.get_extra_info('peername')
        if not peername:
            writer.close()
            return

        addr = f"{peername[0]}:{peername[1]}"
        ip = peername[0]

        # Rate limiting
        if not self.rate_limiter.check(f"connect:{addr}"):
            writer.close()
            return

        # Проверка бана
        if addr in self.banned:
            if time.time() < self.banned[addr]:
                writer.close()
                return
            del self.banned[addr]

        try:
            # ECDH Handshake
            shared_key = await self._perform_handshake(reader, writer, addr)
            if not shared_key:
                return

            # Сохраняем соединение
            self.connections[addr] = {
                "writer": writer,
                "reader": reader,
                "shared_key": shared_key,
                "established": time.time(),
                "ip": ip
            }

            # Отправляем приветствие
            hello_msg = {
                "type": "hello",
                "version": VERSION,
                "height": self.bc.height if self.bc else 0,
                "ip": self.my_ip,
                "port": P2P_PORT,
                "is_white": self.is_white
            }
            await self._send_secure(addr, hello_msg)

            # Основной цикл
            while self.running:
                msg = await self._receive_secure(addr, reader, shared_key)
                if not msg:
                    break

                resp = await self._proc_secure(msg, addr)
                if resp:
                    await self._send_secure(addr, resp)

        except (asyncio.TimeoutError, ConnectionError):
            pass
        except Exception as e:
            log.debug(f"Ошибка обработки {addr}: {e}")
        finally:
            self.connections.pop(addr, None)
            PEERS_GAUGE.set(len(self.connections))
            try:
                writer.close()
            except:
                pass

    async def _perform_handshake(self, reader, writer, addr) -> Optional[bytes]:
        """Выполняет ECDH handshake"""
        try:
            # Отправляем свой публичный ключ
            public_bytes = self.ephemeral_public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            writer.write(struct.pack('>I', len(public_bytes)))
            writer.write(public_bytes)
            await writer.drain()

            # Получаем публичный ключ пира
            length_data = await asyncio.wait_for(reader.read(4), timeout=10)
            if not length_data:
                return None

            length = struct.unpack('>I', length_data)[0]
            if length > 1024:
                return None

            peer_public_bytes = await asyncio.wait_for(reader.read(length), timeout=10)

            # Вычисляем shared key
            shared_key = CryptoUtils.derive_shared_key(
                self.ephemeral_private_key, peer_public_bytes
            )

            log.debug(f"🔐 Защищенный канал установлен с {addr}")
            return shared_key

        except Exception as e:
            log.error(f"Ошибка handshake с {addr}: {e}")
            return None

    async def _send_secure(self, addr: str, msg: dict):
        """Отправляет зашифрованное сообщение"""
        if addr not in self.connections:
            return

        try:
            conn = self.connections[addr]
            plaintext = json.dumps(msg).encode()

            # Шифруем
            encrypted = CryptoUtils.encrypt_message(conn["shared_key"], plaintext)

            # Отправляем с префиксом длины
            conn["writer"].write(struct.pack('>I', len(encrypted)))
            conn["writer"].write(encrypted)
            await conn["writer"].drain()

        except Exception as e:
            log.debug(f"Ошибка отправки {addr}: {e}")
            self.connections.pop(addr, None)

    async def _receive_secure(self, addr: str, reader, shared_key: bytes) -> Optional[dict]:
        """Получает и расшифровывает сообщение"""
        try:
            # Читаем длину
            length_data = await asyncio.wait_for(reader.read(4), timeout=PEER_TIMEOUT)
            if not length_data:
                return None

            length = struct.unpack('>I', length_data)[0]
            if length > 10 * 1024 * 1024:  # Максимум 10MB
                self.penalize(addr, OffenseType.PROTOCOL_VIOLATION)
                return None

            # Читаем данные
            encrypted = await asyncio.wait_for(reader.read(length), timeout=30)

            # Расшифровываем
            plaintext = CryptoUtils.decrypt_message(shared_key, encrypted)

            return json.loads(plaintext.decode())

        except Exception as e:
            log.debug(f"Ошибка получения от {addr}: {e}")
            return None

    async def _proc_secure(self, msg: dict, addr: str) -> Optional[dict]:
        """Обрабатывает сообщения с проверками безопасности"""
        msg_type = msg.get("type")
        peer_ip = msg.get("ip", addr.split(":")[0])
        peer_port = msg.get("port", P2P_PORT)

        # Rate limiting для разных типов сообщений
        if msg_type in ["get_seeds", "seed_announce"]:
            if not self.rate_limiter.check(f"{msg_type}:{addr}", limit=10):
                return None

        if msg_type == "hello":
            return await self._handle_hello(msg, addr, peer_ip, peer_port)
        elif msg_type == "seed_announce":
            return await self._handle_seed_announce(msg, addr)
        elif msg_type == "get_seeds":
            return await self._handle_get_seeds()
        elif msg_type == "seeds_list":
            await self._handle_seeds_list(msg, addr)
        elif msg_type == "get_blocks":
            return await self._handle_get_blocks(msg)
        elif msg_type == "blocks":
            await self._handle_blocks(msg)
        elif msg_type == "new_block":
            await self._handle_new_block(msg, addr)
        elif msg_type == "ping":
            return await self._handle_ping()
        elif msg_type == "seed_confirmation":
            await self._handle_seed_confirmation(msg, addr)
        elif msg_type == "ip_verify":
            return await self._handle_ip_verify(msg)

        return None

    async def _handle_hello(self, msg: dict, addr: str, peer_ip: str, peer_port: int) -> dict:
        """Обрабатывает приветствие"""
        peer_height = msg.get("height", 0)
        peer_is_white = msg.get("is_white", False)

        peer_info = PeerInfo(
            addr=addr, ip=peer_ip, port=peer_port,
            last_seen=time.time(), height=peer_height,
            is_white=peer_is_white, version=msg.get("version", "")
        )

        if peer_is_white:
            self.white_peers[addr] = peer_info

            # Проверяем proof для seed-регистрации
            proof_data = msg.get("seed_proof")
            if proof_data:
                proof = SeedProof(**proof_data)
                await self.seed_registry.add_seed(
                    peer_ip, peer_port, peer_height,
                    msg.get("version", ""), proof
                )

                # Отправляем подтверждение
                if peer_height > 0 and self.seed_registry.reputation.get(addr, 0) > 0:
                    confirm_msg = {
                        "type": "seed_confirmation",
                        "seed_addr": addr,
                        "confirmer_addr": f"{self.my_ip}:{P2P_PORT}"
                    }
                    asyncio.create_task(self._send_secure(addr, confirm_msg))

            # Синхронизация
            if self.bc and peer_height > self.bc.height and not self.syncing:
                asyncio.create_task(self._sync_from_peer(addr))
        else:
            self.grey_peers[addr] = peer_info

        self.peers[addr] = peer_info
        self.peer_db.save_peer(addr, peer_info)
        PEERS_GAUGE.set(len(self.peers))

        # Отправляем топ seed-нод
        seeds = self.seed_registry.get_active_seeds(30, min_reputation=1.0)
        return {
            "type": "hello_ack",
            "version": VERSION,
            "height": self.bc.height if self.bc else 0,
            "is_white": self.is_white,
            "seeds": [{"ip": s.ip, "port": s.port, "height": s.height} for s in seeds],
            "seed_proof": vars(await self._generate_seed_proof()) if self.is_white else None
        }

    async def _handle_seed_announce(self, msg: dict, addr: str) -> Optional[dict]:
        """Обрабатывает анонс seed-ноды"""
        peer_ip = msg.get("ip")
        peer_port = msg.get("port", P2P_PORT)
        proof_data = msg.get("proof")
        msg_hash = msg.get("announce_hash", "")

        # Проверка gossip cache
        if msg_hash and msg_hash in self.gossip_cache:
            if time.time() - self.gossip_cache[msg_hash] < GOSSIP_CACHE_TTL:
                return None

        # Проверка proof
        if proof_data:
            proof = SeedProof(**proof_data)
            await self.seed_registry.add_seed(
                peer_ip, peer_port,
                msg.get("height", 0),
                msg.get("version", ""),
                proof
            )
        else:
            await self.seed_registry.decrease_reputation(addr, 0.5)
            return None

        # Кешируем
        if msg_hash:
            self.gossip_cache[msg_hash] = time.time()

        # Вирусное распространение
        if time.time() - msg.get("timestamp", 0) < 300:
            asyncio.create_task(self._relay_secure(msg, addr))

        return None

    async def _handle_get_seeds(self) -> dict:
        """Отдает seed-ноды с учетом репутации"""
        seeds = self.seed_registry.get_active_seeds(50, min_reputation=1.0)
        return {
            "type": "seeds_list",
            "seeds": [{"ip": s.ip, "port": s.port, "height": s.height} for s in seeds],
            "height": self.bc.height if self.bc else 0,
            "timestamp": time.time()
        }

    async def _handle_seeds_list(self, msg: dict, addr: str):
        """Обрабатывает полученный список seed-нод"""
        seeds = msg.get("seeds", [])

        if len(seeds) > 100:
            self.penalize(addr, OffenseType.SPAM)
            return

        new_seeds = 0
        for seed in seeds[:20]:  # Ограничиваем обработку
            ip = seed.get("ip")
            port = seed.get("port", P2P_PORT)

            if ip == self.my_ip or not IPUtils.is_public_ip(ip):
                continue

            success = await self.seed_registry.add_seed(
                ip, port,
                seed.get("height", 0),
                seed.get("version", ""),
                None, require_verification=False
            )
            if success:
                new_seeds += 1

            if new_seeds <= 10:
                addr_key = f"{ip}:{port}"
                if addr_key not in self.connections:
                    asyncio.create_task(self._connect_secure(ip, port))

    async def _handle_seed_confirmation(self, msg: dict, addr: str):
        """Обрабатывает подтверждение seed-ноды"""
        seed_addr = msg.get("seed_addr")
        confirmer_addr = msg.get("confirmer_addr")

        if seed_addr and confirmer_addr:
            await self.seed_registry.add_confirmation(seed_addr, confirmer_addr)

    async def _handle_ping(self) -> dict:
        """Обрабатывает ping"""
        return {
            "type": "pong",
            "height": self.bc.height if self.bc else 0,
            "is_white": self.is_white,
            "seed_count": len(self.seed_registry.seeds),
            "timestamp": time.time()
        }

    async def _handle_get_blocks(self, msg: dict) -> dict:
        """Отдает блоки для синхронизации"""
        start = msg.get("start_height", 0)
        limit = min(msg.get("limit", 500), 500)

        if self.bc and start < len(self.bc.chain):
            blocks = self.bc.chain[start:start + limit]
            return {
                "type": "blocks",
                "blocks": blocks,
                "height": self.bc.height
            }
        return {"type": "blocks", "blocks": [], "height": 0}

    async def _handle_blocks(self, msg: dict):
        """Обрабатывает полученные блоки"""
        blocks = msg.get("blocks", [])
        if self.bc:
            for block in blocks:
                await self.bc.add_block(block, "sync")

    async def _handle_new_block(self, msg: dict, addr: str):
        """Обрабатывает новый блок"""
        block = msg.get("block")
        if block and self.bc:
            success, _ = await self.bc.add_block(block, "broadcast")
            if not success:
                self.penalize(addr, OffenseType.INVALID_BLOCK)

    async def _handle_ip_verify(self, msg: dict) -> dict:
        """Обрабатывает запрос верификации IP"""
        challenge = msg.get("challenge", "")
        ip = msg.get("ip", "")
        port = msg.get("port", 0)

        proof = hashlib.sha256(
            f"{challenge}:{ip}:{port}:RAMCOIN_VERIFY".encode()
        ).hexdigest()

        return {
            "type": "ip_verify_ack",
            "proof": proof,
            "timestamp": int(time.time())
        }

    async def _relay_secure(self, msg: dict, exclude_addr: str):
        """Безопасная ретрансляция"""
        msg_hash = msg.get("announce_hash", "")
        if msg_hash and msg_hash in self.gossip_cache:
            if time.time() - self.gossip_cache[msg_hash] < GOSSIP_CACHE_TTL:
                return

        relayed = 0
        for addr, conn in list(self.connections.items()):
            if addr != exclude_addr and relayed < MAX_RELAY_COUNT:
                try:
                    await self._send_secure(addr, msg)
                    relayed += 1
                except:
                    pass

        if msg_hash:
            self.gossip_cache[msg_hash] = time.time()

    async def _connect_secure(self, ip: str, port: int):
        """Устанавливает защищенное соединение"""
        addr = f"{ip}:{port}"
        if ip == self.my_ip or addr in self.connections:
            return

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=10
            )

            # ECDH Handshake
            shared_key = await self._perform_handshake(reader, writer, addr)
            if not shared_key:
                writer.close()
                return

            self.connections[addr] = {
                "writer": writer,
                "reader": reader,
                "shared_key": shared_key,
                "established": time.time(),
                "ip": ip
            }

            # Отправляем приветствие
            hello_msg = {
                "type": "hello",
                "version": VERSION,
                "height": self.bc.height if self.bc else 0,
                "ip": self.my_ip,
                "port": P2P_PORT,
                "is_white": self.is_white,
                "seed_proof": vars(await self._generate_seed_proof()) if self.is_white else None
            }
            await self._send_secure(addr, hello_msg)

            log.info(f"🔗 Подключены к {addr}")
            PEERS_GAUGE.set(len(self.connections))

        except Exception as e:
            log.debug(f"Не удалось подключиться к {addr}: {e}")

    async def _sync_from_peer(self, addr: str):
        """Синхронизация блоков"""
        if self.syncing:
            return

        self.syncing = True
        try:
            await self._send_secure(addr, {
                "type": "get_blocks",
                "start_height": self.bc.height,
                "limit": 500
            })

            for _ in range(60):
                await asyncio.sleep(1)
                if self.bc.height >= self.peers.get(addr, PeerInfo(addr, "", 0)).height:
                    break
        finally:
            self.syncing = False

    async def _announce_loop(self):
        """Периодически анонсирует себя в сети"""
        await asyncio.sleep(30)
        while self.running:
            try:
                if self.is_white and self.bc:
                    proof = await self._generate_seed_proof()
                    await self.seed_registry.add_seed(
                        self.my_ip, P2P_PORT,
                        self.bc.height, VERSION, proof
                    )

                    announce = {
                        "type": "seed_announce",
                        "ip": self.my_ip,
                        "port": P2P_PORT,
                        "height": self.bc.height,
                        "version": VERSION,
                        "timestamp": time.time(),
                        "proof": vars(proof),
                        "announce_hash": hashlib.sha256(
                            f"{self.my_ip}:{P2P_PORT}:{time.time()}:{secrets.token_hex(8)}".encode()
                        ).hexdigest()
                    }
                    await self._broadcast_secure(announce)

                    log.debug(f"📢 Анонс отправлен. Seed-нод: {len(self.seed_registry.seeds)}")

                await asyncio.sleep(ANNOUNCE_INTERVAL)
            except Exception as e:
                log.error(f"Ошибка в announce loop: {e}")
                await asyncio.sleep(60)

    async def _seed_cleanup_loop(self):
        """Периодическая очистка seed-нод"""
        while self.running:
            await asyncio.sleep(3600)
            await self.seed_registry.cleanup()

    async def _gossip_cleanup_loop(self):
        """Очистка gossip cache"""
        while self.running:
            await asyncio.sleep(600)
            now = time.time()
            self.gossip_cache = {
                k: v for k, v in self.gossip_cache.items()
                if now - v < GOSSIP_CACHE_TTL
            }

    async def _health_check_loop(self):
        """Периодическая проверка здоровья сети"""
        while self.running:
            await asyncio.sleep(300)  # Каждые 5 минут
            try:
                health = await self.health_monitor.check_network_health()
                log.info(f"🏥 Здоровье сети: {health.status.value} (score: {health.health_score:.2f})")

                if health.status == NetworkHealth.CRITICAL:
                    log.critical("🚨 КРИТИЧЕСКОЕ состояние сети!")
            except Exception as e:
                log.error(f"Ошибка проверки здоровья: {e}")

    async def _metrics_update_loop(self):
        """Обновление метрик"""
        while self.running:
            await asyncio.sleep(60)
            try:
                if self.bc:
                    HEIGHT_GAUGE.set(self.bc.height)
                    MEMPOOL_SIZE.set(len(self.bc.mempool))

                PEERS_GAUGE.set(len(self.connections))
                SEEDS_GAUGE.set(len(self.seed_registry.seeds))

                # Средняя репутация
                if self.seed_registry.reputation:
                    avg_rep = sum(self.seed_registry.reputation.values()) / len(self.seed_registry.reputation)
                    REPUTATION_GAUGE.set(avg_rep)
            except:
                pass

    async def _peer_discovery_loop(self):
        """Поиск новых пиров"""
        await asyncio.sleep(60)
        while self.running:
            try:
                for addr, conn in list(self.connections.items())[:5]:
                    try:
                        await self._send_secure(addr, {"type": "get_seeds"})
                    except:
                        pass

                await asyncio.sleep(300)
            except Exception as e:
                log.error(f"Ошибка в discovery loop: {e}")
                await asyncio.sleep(60)

    async def _broadcast_secure(self, msg: dict):
        """Широковещательная рассылка"""
        dead = []
        for addr, conn in list(self.connections.items()):
            try:
                await self._send_secure(addr, msg)
            except:
                dead.append(addr)

        for addr in dead:
            self.connections.pop(addr, None)

    async def broadcast_block(self, block):
        """Рассылка нового блока"""
        await self._broadcast_secure({"type": "new_block", "block": block})

    def penalize(self, addr: str, offense: OffenseType = OffenseType.PROTOCOL_VIOLATION):
        """Штрафует ноду за плохое поведение"""
        self.scores[addr] += 1

        # Градуированное наказание через seed-регистр
        asyncio.create_task(self.seed_registry.graduated_penalty(addr, offense))

        if self.scores[addr] >= 5:
            self.banned[addr] = time.time() + 3600
            log.info(f"🚫 Забанен: {addr}")

    def get_seeds_for_api(self):
        """Возвращает список seed-нод для API"""
        seeds = self.seed_registry.get_active_seeds(100, min_reputation=1.0)
        return {
            "seeds": [
                {"ip": s.ip, "port": s.port, "height": s.height}
                for s in seeds[:20]
            ],
            "total": len(seeds),
            "my_ip": self.my_ip if self.is_white else "hidden",
            "is_white": self.is_white,
            "height": self.bc.height if self.bc else 0
        }

    def get_network_health(self) -> dict:
        """Возвращает статус здоровья сети"""
        health = self.health_monitor.health_history[-1] if self.health_monitor.health_history else None

        return {
            "status": health.status.value if health else "unknown",
            "score": health.health_score if health else 0,
            "peers": len(self.connections),
            "seeds_active": len(self.seed_registry.get_active_seeds(100)),
            "alerts": len(self.anomaly_detector.get_recent_alerts(60)),
            "timestamp": time.time()
        }

    async def stop(self):
        """Останавливает P2P менеджер"""
        self.running = False
        for conn in self.connections.values():
            try:
                conn["writer"].close()
            except:
                pass
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        if self.ssl_server:
            self.ssl_server.close()
            await self.ssl_server.wait_closed()


class PeerDB:
    """БД для хранения пиров"""

    def __init__(self):
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(PEERS_DB) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS peers 
                          (addr TEXT PRIMARY KEY, ip TEXT, port INTEGER, 
                           last_seen REAL, height INTEGER, is_white INTEGER,
                           version TEXT)''')
            conn.execute('PRAGMA journal_mode=WAL')

    def load_peers(self) -> dict:
        try:
            with sqlite3.connect(PEERS_DB) as conn:
                rows = conn.execute(
                    "SELECT addr, ip, port, last_seen, height, is_white, version FROM peers"
                ).fetchall()

                peers = {}
                for row in rows:
                    addr, ip, port, last_seen, height, is_white, version = row
                    peers[addr] = {
                        "ip": ip, "port": port,
                        "last_seen": last_seen,
                        "height": height,
                        "is_white": bool(is_white),
                        "version": version
                    }
                return peers
        except:
            return {}

    def save_peer(self, addr: str, info: PeerInfo):
        try:
            with sqlite3.connect(PEERS_DB, timeout=10) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO peers VALUES (?,?,?,?,?,?,?)",
                    (addr, info.ip, info.port,
                     info.last_seen,
                     info.height,
                     1 if info.is_white else 0,
                     info.version)
                )
        except:
            pass


# ==================== API ====================
async def handle_chain(request):
    return web.json_response(request.app['bc'].get_stats())


async def handle_stats(request):
    return web.json_response(request.app['bc'].get_stats())


async def handle_health(request):
    bc = request.app['bc']
    p2p = request.app.get('p2p')
    health_data = {
        "ok": True,
        "version": VERSION,
        "height": bc.height,
        "uptime": int(time.time() - bc.start_time)
    }
    if p2p:
        health_data["network_health"] = p2p.get_network_health()
    return web.json_response(health_data)


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
    return web.json_response([
        {"address": a, "balance": b / COIN}
        for a, b in sorted(bc.accounts.items(), key=lambda x: x[1], reverse=True)[:lim]
    ])


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
    if not bc.verify_tx_signature(d):
        return web.json_response({"status": "rejected", "reason": "invalid signature"}, status=400)
    async with bc.mempool_lock:
        bc.mempool.append(d)
        bc.mempool_hashes.add(d.get("signature", ""))
    MEMPOOL_SIZE.set(len(bc.mempool))
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
    ok = await bc.submit_share(
        a, int(d.get("nonce", 0)), int(d.get("nonce_seed", 0)),
        d.get("mix", "0"), int(d.get("mods", 0)),
        int(d.get("extra_nonce", 0)), int(d.get("scratchpad_size", BASE_SCRATCHPAD))
    )
    return web.json_response({"status": "ok" if ok else "rejected"})


async def handle_pool_stats(request):
    bc = request.app['bc']
    return web.json_response({"shares": bc.pool_total, "miners": len(bc.pool_shares)})


async def handle_seeds(request):
    """Отдает список seed-нод"""
    bc = request.app['bc']
    if bc.p2p:
        return web.json_response(bc.p2p.get_seeds_for_api())
    return web.json_response({"seeds": [], "total": 0})


async def handle_network(request):
    """Статус сети"""
    bc = request.app['bc']
    p2p = bc.p2p
    return web.json_response({
        "my_ip": p2p.my_ip if p2p.is_white else "hidden",
        "is_white": p2p.is_white,
        "height": bc.height,
        "peers": len(p2p.connections),
        "active_seeds": len(p2p.seed_registry.get_active_seeds()),
        "health": p2p.get_network_health(),
        "seed_stats": p2p.seed_registry.get_stats()
    })


async def handle_alerts(request):
    """Аномалии сети"""
    bc = request.app['bc']
    if bc.p2p:
        alerts = bc.p2p.anomaly_detector.get_recent_alerts(60)
        return web.json_response({"alerts": alerts, "count": len(alerts)})
    return web.json_response({"alerts": [], "count": 0})


async def handle_ws(request):
    bc = request.app['bc']
    ws = web.WebSocketResponse(heartbeat=30, timeout=60)
    await ws.prepare(request)
    bc.ws_clients.add(ws)
    log.info(f"🔌 WS клиент (всего: {len(bc.ws_clients)})")
    try:
        await ws.send_json({
            "event": "connected",
            "height": bc.height,
            "target": bc.target,
            "version": VERSION
        })
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
        self.p2p = SecurePeerManager()
        self.bc = Blockchain(self.p2p)
        self.p2p.bc = self.bc
        self.running = False

    async def start(self):
        self.running = True
        app = web.Application(client_max_size=10 * 1024 * 1024)
        app['bc'] = self.bc
        app['p2p'] = self.p2p

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
        app.router.add_get('/seeds', handle_seeds)
        app.router.add_get('/network', handle_network)
        app.router.add_get('/alerts', handle_alerts)
        app.router.add_get('/ws', handle_ws)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", API_PORT)
        await site.start()

        # Запускаем Prometheus метрики
        start_http_server(METRICS_PORT)

        log.info(f"🌐 API: http://0.0.0.0:{API_PORT}")
        log.info(f"📊 Метрики: http://0.0.0.0:{METRICS_PORT}")
        log.info(f"🔒 P2P: 0.0.0.0:{P2P_PORT}")

        await self.p2p.start_server("0.0.0.0", P2P_PORT)

        log.info(f"""
╔══════════════════════════════════════════╗
║   RAMCOIN NODE v{VERSION}              ║
║   Ультра-защищенная P2P-сеть            ║
║   Шифрование: ChaCha20-Poly1305        ║
║   Квантово-устойчивое резервирование   ║
║   IP: {self.p2p.my_ip} ({'БЕЛЫЙ' if self.p2p.is_white else 'СЕРЫЙ'})          ║
║   H: {self.bc.height}                            ║
║   Seed-нод: {len(self.p2p.seed_registry.seeds)}                           ║
╚══════════════════════════════════════════╝
        """)

        # Обработка сигналов для graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
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
    """Точка входа с поддержкой Windows"""
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        log.info("🚀 Используется uvloop для максимальной производительности")
    except ImportError:
        log.info("⚠️ Windows detected: используется стандартный event loop")
        log.info("  (uvloop недоступен на Windows, это нормально)")

    node = Node()
    await node.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bye")
    except Exception as e:
        log.critical(f"💥 Fatal: {e}", exc_info=True)