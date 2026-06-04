# ⚡ RAMCOIN (RAM) — P2P Blockchain Cryptocurrency

**Версия:** v9.0.15 | **Сеть:** LIVE | **Блоков:** 14359+

---

## 📊 Что такое RAMCOIN?

**RAMCOIN** — полностью децентрализованная P2P криптовалюта с защитой от ASIC/FPGA майнинга.

- ⚡ **Алгоритм:** RAM-Hash (Memory-Hard, только CPU)
- 💎 **Макс. эмиссия:** 17 520 000 RAM
- ⏱️ **Время блока:** ~30 секунд
- 🔥 **Сжигание:** 1% от каждой награды
- 🔒 **Безопасность:** ECDSA + SHA256
- 🛡️ **ASIC защита:** 512KB-4MB scratchpad

---

## 🚀 Быстрый старт

### 1. Скачай и запусти Кошелёк
RAMCOIN_Wallet.exe

text
Создай RAM адрес для майнинга

### 2. Скачай и запусти Майнер
RAMCOIN_Miner.exe

text
Выбери SOLO или POOL режим

### 3. Зарабатывай RAM!
Майнер автоматически подключается к сети!

---

## 📥 Скачать

| Файл | Описание |
|------|----------|
| [💼 RAMCOIN_Wallet.exe](https://github.com/ramcoinnode-debug/ramcoin/releases/latest) | Кошелёк для создания адреса |
| [⛏️ RAMCOIN_Miner.exe](https://github.com/ramcoinnode-debug/ramcoin/releases/latest) | Майнер SOLO/POOL |
| [🌐 RAMCOIN_Node.exe](https://github.com/ramcoinnode-debug/ramcoin/releases/latest) | Нода (для белых IP) |

Или скачай исходный код:
- `wallet.py` — Кошелёк
- `miner.py` — Майнер
- `ramcoin_full.py` — Нода

---

## 💎 Режимы майнинга

### ⛏️ SOLO
- Находишь блок → получаешь **10 RAM**
- Для мощных ПК
- Полная награда твоя

### 👥 POOL
- Отправляешь шары → стабильный доход
- Для любых ПК
- Награда распределяется по шарам

---

## 📊 Характеристики

| Параметр | Значение |
|----------|----------|
| Алгоритм | RAM-Hash (Memory-Hard) |
| Макс. supply | 17,520,000 RAM |
| Время блока | ~30 секунд |
| Награда за блок | 10 RAM |
| Халвинг | Каждые 876,000 блоков |
| Сжигание | 1% от награды |
| Комиссия DEV | 10% от транзакций |
| Pool fee | 1% |
| Размер скретчпада | 512KB - 4MB |
| Итераций | 8,192 |
| Подпись | ECDSA (secp256k1) |
| Хеширование | SHA256 |

---

## 🌐 Сеть

### Seed ноды:
- `90.188.115.169:5000` (API)
- `90.188.108.252:5000` (API)
- Порт P2P: `8333`

### Типы участников:
- **Белые IP** — полные ноды, хранят и раздают блокчейн
- **Серые IP** — майнеры за NAT, подключаются к белым

---

## 🔧 Запуск из исходного кода

### Требования:
```bash
pip install -r requirements.txt
requirements.txt:
text
aiohttp
cryptography
pycryptodome
websocket-client
psutil
Запуск:
bash
# Нода
python ramcoin_full.py

# Майнер
python miner.py

# Кошелёк
python wallet.py
🏗️ Сборка .exe
bash
pip install pyinstaller

pyinstaller --onefile --name "RAMCOIN_Wallet" wallet.py
pyinstaller --onefile --name "RAMCOIN_Miner" miner.py
pyinstaller --onefile --name "RAMCOIN_Node" ramcoin_full.py
Готовые файлы в папке dist/

🛡️ Безопасность
✅ Проверка подписей блоков (ECDSA)

✅ Проверка подписей транзакций

✅ Защита от двойных трат (nonce)

✅ Защита от форков

✅ Орфанные блоки

✅ Memory-Hard PoW (ASIC/FPGA resistant)

✅ Шифрование кошелька (AES-256-GCM)

🌍 Сообщество
💬 Telegram: t.me/ramcoin_pow

🌐 Сайт: ramcoin.netlify.app

📦 GitHub: github.com/ramcoinnode-debug/ramcoin

🎬 Rutube: rutube.ru/channel/38441251

🎮 Twitch: twitch.tv/ram_coin

🟢 Kick: kick.com/ram_coin

⚠️ Важно
Windows Defender может показать предупреждение на .exe файлы — это нормально для самоподписанных приложений.

Нажмите "Подробнее" → "Выполнить в любом случае"

📈 Статистика сети
Актуальная статистика доступна по адресу:

text
http://90.188.115.169:5000/stats
RAMCOIN © 2026 — Крипта для народа! Майнь на своём ПК! ⚡💰
