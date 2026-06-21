# 🪙 RAMCOIN v10.3.0

![Version](https://img.shields.io/badge/version-10.3.0-blue)
![Protocol](https://img.shields.io/badge/protocol-2-green)
![License](https://img.shields.io/badge/license-MIT-purple)
![Python](https://img.shields.io/badge/python-3.10%2B-yellow)

**Децентрализованная криптовалюта с защищённой P2P-сетью и алгоритмом Ramhash v7 (Memory-hard PoW).**

---

## 🚀 Особенности

- **Алгоритм**: Ramhash v7 (Memory-hard, ASIC/FPGA-resistant)
- **Шифрование P2P**: ChaCha20-Poly1305 + ECDH
- **Защита от атак**: Eclipse, Sybil, DDoS
- **Градуированная репутационная система** для seed-нод
- **Anti-cheat**: Проверка потоков, RAM, модификаций
- **WebSocket**: Реал-тайм уведомления о блоках
- **Prometheus**: Метрики для мониторинга
- **Квантово-устойчивое резервирование**

---

## 📊 Параметры сети

| Параметр | Значение |
|----------|----------|
| **Ticker** | RAM |
| **Блок** | 30 секунд |
| **Награда** | 10 RAM (уменьшается вдвое каждые 876 000 блоков) |
| **Халвинг** | 876 000 блоков (~304 дня) |
| **Количество халвингов** | 64 |
| **Max supply** | ~17 520 000 RAM |
| **Current supply** | ~202 530 RAM (динамически) |
| **Алгоритм** | Ramhash v7 (Memory-hard) |
| **Scratchpad** | 524 KB — 4 MB |
| **Комиссия сети** | 0.001 RAM |
| **Порт P2P** | 8333 |
| **Порт API** | 5000 |
| **Порт Metrics** | 9090 |
| **Мин. Python** | 3.10+ |

### Расчёт эмиссии
Эпоха 1: 876 000 × 10.00000000 = 8 760 000 RAM
Эпоха 2: 876 000 × 5.00000000 = 4 380 000 RAM
Эпоха 3: 876 000 × 2.50000000 = 2 190 000 RAM
Эпоха 4: 876 000 × 1.25000000 = 1 095 000 RAM
...
Всего 64 эпохи ≈ 17 520 000 RAM

text

---

## 📦 Компоненты

| Файл | Версия | Описание |
|------|--------|----------|
| `node.py` | v10.3.0 | 🖥️ Нода (блокчейн + P2P + API) |
| `miner.py` | v30.0.3 | ⛏️ Майнер (SOLO + POOL) |
| `wallet.py` | v8.0.0 | 💼 Кошелёк (AES-256-GCM) |

---

## 🔧 Установка

```bash
# Клонирование репозитория
git clone https://github.com/ramcoinnode-debug/ramcoin.git
cd ramcoin

# Установка зависимостей
pip install -r requirements.txt
requirements.txt
txt
aiohttp>=3.9.0
lz4>=4.3.0
cryptography>=41.0.0
psutil>=5.9.0
pycryptodome>=3.19.0
prometheus-client>=0.19.0
pyyaml>=6.0
🖥️ Быстрый старт
1. Запуск ноды
bash
# Стандартный запуск
python node.py

# С белым IP (для работы как seed-нода)
# Linux/Mac:
export RAMCOIN_IP=ваш.публичный.ip
python node.py

# Windows:
set RAMCOIN_IP=ваш.публичный.ip
python node.py

# Кастомные порты
P2P_PORT=8333 API_PORT=5000 METRICS_PORT=9090 python node.py
Ожидаемый вывод:

text
✅ RAMCOIN v10.3.0 | H:20487 | D:6.07 KRam/s | Аккаунтов: 11
🌐 API: http://0.0.0.0:5000
🔑 API-Key: a1b2c3d4e5f6... (сохранён в api_key.txt)
🔒 P2P сервер: 0.0.0.0:8333
📊 Метрики: http://0.0.0.0:9090

╔══════════════════════════════════════════╗
║   RAMCOIN NODE v10.3.0                  ║
║   📍 IP: ваш.ip.адрес (БЕЛЫЙ)           ║
║   📦 H: 20487                           ║
║   💰 Reward: 10.0 RAM                   ║
║   🔒 Security: MAXIMUM                  ║
╚══════════════════════════════════════════╝
2. Запуск майнера
bash
python miner.py
Интерактивная настройка:

text
╔══════════════════════════════════════════════╗
║   RAMCOIN MINER v30.0.3                     ║
╚══════════════════════════════════════════════╝

Node: v10.3.0 H:#20487

1. SOLO (full reward)
2. POOL (stable shares)
Choose [1/2]: 1

RAM_ address: RAM_ваш_адрес
Private key (64 hex): ваш_приватный_ключ_64_символа

Syncing...
Ready! Block #20487 | Diff: 6.07K | Reward: 10.0 RAM
Using 4 threads (MAX_THREADS_PER_MINER = 4)
🚀 MINING STARTED!
4 mining threads started

[00:15:30] SOLO 2.45 MH/s | Block:#20487 | OK:3/Fail:0 | Diff:6.07K | Daily:0.1234 RAM | Node:OK
Формат вывода майнера:

Сегмент	Описание
[00:15:30]	Время работы (часы:минуты:секунды)
SOLO/POOL	Режим майнинга
2.45 MH/s	Текущая скорость хеширования
Block:#20487	Текущая высота блокчейна
OK:3	Количество принятых блоков
Fail:0	Количество отклонённых блоков
Diff:6.07K	Текущая сложность сети
Daily:0.1234	Ожидаемая награда за 24 часа
Node:OK	Статус соединения с нодой
3. Запуск кошелька
bash
python wallet.py
Создание нового кошелька:

text
╔══════════════════════════════════════╗
║   RAMCOIN WALLET v8.0.0             ║
║   Titan Edition • Максимум защиты   ║
╚══════════════════════════════════════╝

🆕 СОЗДАНИЕ НОВОГО КОШЕЛЬКА

⚠️  ЗАПИШИТЕ ЭТИ 12 СЛОВ! Они не сохраняются!
📝 abandon ability able about above absent absorb abstract absurd abuse access accident

Нажмите ENTER когда записали...

🔒 Придумайте пароль (мин. 8 символов):
👉 ********
🔒 Повторите пароль:
👉 ********

✅ Кошелёк создан!
📍 Адрес: RAM_04a9b30816a61686f377f152435f528e...
Меню кошелька:

text
=======================================================
💼 RAMCOIN WALLET v8.0.0
=======================================================
📍 RAM_04a9b30816a6...
⛽ Комиссия сети: 0.001 RAM
-------------------------------------------------------
1. 💰 Проверить баланс
2. 📤 Отправить RAM
3. 📒 Адресная книга
4. 📋 Информация о кошельке
5. 🔒 Сменить пароль
6. 🚪 Выйти
-------------------------------------------------------
👉
🌐 API
Полный список эндпоинтов
Endpoint	Метод	API-Key	Описание
/health	GET	Нет	Здоровье ноды
/chain	GET	Нет	Блокчейн (последние 10 блоков)
/stats	GET	Нет	Полная статистика сети
/coininfo	GET	Нет	Информация о монете
/block/{idx}	GET	Нет	Блок по индексу
/address/{addr}	GET	Нет	Баланс и nonce адреса
/pending	GET	Нет	Неподтверждённые транзакции
/top	GET	Нет	Топ богатых адресов
/pool/template	GET	Нет	Шаблон для POOL майнинга
/pool/share	POST	Нет	Отправка шары в пул
/pool/stats	GET	Нет	Статистика пула
/mine	POST	Да	Отправка блока (SOLO майнинг)
/tx	POST	Нет	Отправка транзакции
/seeds	GET	Нет	Список активных seed-нод
/network	GET	Нет	Состояние P2P сети
/ws	WS	Нет	WebSocket уведомления
Примеры запросов
Здоровье ноды
bash
curl http://localhost:5000/health
json
{
  "ok": true,
  "version": "10.3.0",
  "height": 20487,
  "uptime": 9003,
  "peers": 0,
  "mempool": 0
}
Информация о блокчейне
bash
curl http://localhost:5000/chain
json
{
  "version": "10.3.0",
  "height": 20487,
  "difficulty": "6.07 KRam/s",
  "total_supply": 202530.0,
  "accounts": 11,
  "peers": 0,
  "miners": 0,
  "mempool": 0,
  "transactions": 10,
  "blocks": 20204,
  "uptime": 9003,
  "reward": 10.0,
  "pool": {
    "shares": 0,
    "miners": 0
  },
  "burn": 1.7,
  "current_target": "19070864726149454124063874679918124821656974130005537118670383644292415488",
  "chain": [...],
  "length": 20487
}
Баланс адреса
bash
curl http://localhost:5000/address/RAM_04a9b...
json
{
  "address": "RAM_04a9b...",
  "balance": 100.0,
  "nonce": 5
}
Статистика сети
bash
curl http://localhost:5000/stats
Информация о монете
bash
curl http://localhost:5000/coininfo
json
{
  "name": "RAMCOIN",
  "symbol": "RAM",
  "algorithm": "Ramhash v7 (Memory-hard)",
  "block_time": 30,
  "block_reward": 10.0,
  "current_supply": 202530.0,
  "max_supply": 17520000,
  "height": 20487,
  "difficulty": "6.07 KRam/s",
  "peers": 0,
  "protocol": 2,
  "version": "10.3.0",
  "halving": 876000
}
Топ адресов
bash
curl http://localhost:5000/top?limit=10
Мемпул
bash
curl http://localhost:5000/pending
Шаблон для пула
bash
curl http://localhost:5000/pool/template
Отправка SOLO блока
bash
curl -X POST http://localhost:5000/mine \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ваш-api-ключ" \
  -d '{
    "index": 20487,
    "previous_hash": "c11a24c8482d85a188e71ac38c40bac0161c5320e8ac64f16530bd2e70586778",
    "transactions": [],
    "timestamp": 1782052992,
    "nonce": 142450499292073,
    "nonce_seed": 3888991796,
    "memory_proof": "000b7eb7aa7c6f560f4e7c71c46b91466c36bdc69d6a70fec51afa8eb6e92a80",
    "target": 19070864726149454124063874679918124821656974130005537118670383644292415488,
    "extra_nonce": 2,
    "miner_payout_address": "RAM_...",
    "scratchpad_mods": 8224,
    "scratchpad_size": 524288,
    "pool_block": false,
    "threads_used": 4,
    "version": 2,
    "miner_signature": "3046022100ba5aaef38bd081a4f1e09893aa930b0b83c76a94995d429d7065c1debd8317e80221009c5dc257394024f9aa7a29885297efc01a2ed54c33b9b85e3e90b1f349ee5073"
  }'
Отправка транзакции
bash
curl -X POST http://localhost:5000/tx \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "RAM_ваш_адрес",
    "recipient": "RAM_адрес_получателя",
    "amount": 100000000,
    "fee": 100000,
    "nonce": 0,
    "timestamp": 1782052992,
    "signature": "3045..."
  }'
WebSocket
bash
# Подключение
wscat -c ws://localhost:5000/ws

# Входящие сообщения:
{"event":"connected","height":20487,"target":"...","version":"10.3.0"}
{"event":"new_block","height":20488,"hash":"000...","target":"..."}
Состояние сети
bash
curl http://localhost:5000/network
Список seed-нод
bash
curl http://localhost:5000/seeds
📊 Мониторинг
Prometheus метрики
bash
# Метрики доступны на порту 9090
curl http://localhost:9090/metrics
Основные метрики:

prometheus
# Статус
ramcoin_height 20487
ramcoin_peers_total 5
ramcoin_connections_active 3
ramcoin_seeds_total 12
ramcoin_average_reputation 85.5

# Производительность
ramcoin_mempool_size 0
ramcoin_block_time_seconds 30.5

# Счётчики
ramcoin_blocks_total{status="accepted"} 20204
ramcoin_blocks_total{status="rejected"} 283
ramcoin_transactions_total 10
ramcoin_api_requests_total{endpoint="/chain",status="ok"} 1234
ramcoin_errors_total{type="invalid_block"} 15
Grafana Dashboard
bash
# 1. Настройте Prometheus (prometheus.yml):
scrape_configs:
  - job_name: 'ramcoin'
    static_configs:
      - targets: ['localhost:9090']

# 2. Импортируйте dashboard в Grafana
# 3. Настройте панели:
#    - Высота блокчейна
#    - Количество пиров
#    - Время между блоками
#    - Размер мемпула
#    - Скорость майнинга
🔐 Безопасность
Уровни защиты
Компонент	Технология	Описание
P2P	ChaCha20-Poly1305 + ECDH	Шифрование всех P2P сообщений
API	API-Key + Rate Limiting	30 запросов/мин, бан при превышении
DDoS	IP-based бан	Автоматический бан на 1 час
Кошелёк	AES-256-GCM + PBKDF2-SHA512	600 000 итераций для пароля
Подписи	ECDSA (secp256k1)	Все блоки и транзакции подписываются
Seed-ноды	Репутационная система	Защита от Sybil атак
Anti-Cheat майнинг
Нода автоматически проверяет каждый блок:

python
# Лимиты майнинга
MAX_THREADS_PER_MINER = 4       # Максимум потоков
MAX_SCRATCHPAD_SIZE = 8388608   # Максимум RAM (8 MB)
EXPECTED_MODS = 8224            # Точное количество модификаций scratchpad

# Блок будет ОТКЛОНЁН если:
❌ threads_used > 4                    # Слишком много потоков
❌ scratchpad_size > 8 388 608         # Слишком много RAM
❌ scratchpad_mods != 8224             # Неверный PoW
❌ memory_proof не проходит проверку   # Поддельный хеш
❌ miner_signature неверная            # Поддельная подпись
❌ previous_hash не совпадает          # Не тот родительский блок
❌ timestamp > now + 7200              # Блок из будущего
📂 Структура проекта
text
ramcoin/
│
├── node.py                  # 🖥️ Нода (сервер блокчейна)
├── miner.py                 # ⛏️ Майнер (клиент для майнинга)
├── wallet.py                # 💼 Кошелёк (управление средствами)
│
├── requirements.txt         # 📦 Python зависимости
├── README.md               # 📖 Документация (этот файл)
├── LICENSE                 # 📜 Лицензия MIT
│
├── api_key.txt              # 🔑 API ключ (автогенерация при первом запуске)
├── blockchain_v7.db         # 💾 Блокчейн (SQLite, все блоки)
├── peers_v9.db              # 👥 Пиры (SQLite, известные ноды)
├── seeds_v11.db             # 🌱 Seed-ноды (SQLite, репутация)
│
├── ramcoin_wallet.json      # 💼 Зашифрованный файл кошелька
├── ramcoin_address_book.json # 📒 Адресная книга контактов
├── mining_progress.json     # 📊 Прогресс и статистика майнинга
└── miner_checkpoint.json    # 💾 Чекпоинт состояния майнера
🧪 Тестирование
Полная локальная сеть
bash
# Терминал 1: Запуск ноды
python node.py

# Терминал 2: Майнер (SOLO)
python miner.py
# Выбрать: 1 (SOLO)
# Ввести: адрес кошелька
# Ввести: приватный ключ

# Терминал 3: Мониторинг API
watch -n 5 'curl -s http://localhost:5000/health | python -m json.tool'
watch -n 10 'curl -s http://localhost:5000/chain | python -m json.tool | head -20'

# Терминал 4: Кошелёк
python wallet.py
# Проверить баланс, отправить транзакцию

# Терминал 5: WebSocket
wscat -c ws://localhost:5000/ws
# Наблюдать новые блоки в реальном времени
Проверка PoW
bash
# Создать тестовый блок
cat > test_block.json << 'EOF'
{
  "index": 20487,
  "previous_hash": "c11a24c8482d85a188e71ac38c40bac0161c5320e8ac64f16530bd2e70586778",
  "transactions": [],
  "timestamp": 1782052992,
  "nonce": 142450499292073,
  "nonce_seed": 3888991796,
  "memory_proof": "000b7eb7aa7c6f560f4e7c71c46b91466c36bdc69d6a70fec51afa8eb6e92a80",
  "target": 19070864726149454124063874679918124821656974130005537118670383644292415488,
  "extra_nonce": 2,
  "miner_payout_address": "RAM_...",
  "scratchpad_mods": 8224,
  "scratchpad_size": 524288,
  "pool_block": false,
  "threads_used": 4,
  "version": 2,
  "miner_signature": "..."
}
EOF

# Отправить на ноду
curl -X POST http://localhost:5000/mine \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ваш-api-ключ" \
  -d @test_block.json

# Ожидаемый ответ:
# {"status": "ok"} — блок принят
# {"status": "rejected", "reason": "..."} — отклонён с причиной
❓ FAQ
<details> <summary><b>Как начать майнить?</b></summary>
Запустите ноду: python node.py

Создайте кошелёк: python wallet.py

Запустите майнер: python miner.py

Выберите SOLO и введите данные кошелька

Майнинг начнётся автоматически

</details><details> <summary><b>Как создать кошелёк?</b></summary>
bash
python wallet.py
Выберите "Создать новый", запишите 12 слов мнемоники, придумайте пароль.

</details><details> <summary><b>Как восстановить кошелёк?</b></summary>
bash
python wallet.py
Выберите "Восстановить по мнемонике", введите 12 слов.

</details><details> <summary><b>Где хранится блокчейн?</b></summary>
В файле blockchain_v7.db (SQLite база данных).

</details><details> <summary><b>Как сбросить блокчейн?</b></summary>
bash
# Остановите ноду (Ctrl+C)
rm blockchain_v7.db
python node.py  # Создаст новый genesis блок
</details><details> <summary><b>Почему блоки отклоняются?</b></summary>
Возможные причины:

threads_used > 4 — превышен лимит потоков

scratchpad_mods != 8224 — неверный PoW

scratchpad_size > 8388608 — превышен лимит RAM

Неверная подпись блока

Неверный previous_hash

Блок из будущего (timestamp > текущее время + 2 часа)

</details><details> <summary><b>Что такое scratchpad_mods?</b></summary>
Количество модификаций scratchpad в процессе PoW. Должно быть строго 8224 (8192 + 32 + 0).

</details><details> <summary><b>Как работает халвинг?</b></summary>
Каждые 876 000 блоков (~304 дня) награда уменьшается вдвое:

Эпоха 1: 10 RAM

Эпоха 2: 5 RAM

Эпоха 3: 2.5 RAM

...

Эпоха 64: ~0 RAM

Всего 64 эпохи, максимальная эмиссия ~17 520 000 RAM.

</details><details> <summary><b>Как подключить Prometheus/Grafana?</b></summary>
yaml
# prometheus.yml
scrape_configs:
  - job_name: 'ramcoin'
    static_configs:
      - targets: ['localhost:9090']
Метрики доступны на http://localhost:9090/metrics.

</details><details> <summary><b>Как запустить seed-ноду?</b></summary>
bash
export RAMCOIN_IP=ваш.публичный.ip
python node.py
Нода автоматически зарегистрируется как seed если IP публичный.

</details>
🔗 Ссылки
Website: https://ramcoin.network

GitHub: https://github.com/ramcoinnode-debug/ramcoin

Discord: https://discord.gg/ramcoin

Twitter: https://twitter.com/ramcoin

🤝 Вклад в проект
Форкните репозиторий

Создайте ветку (git checkout -b feature/новая-фича)

Закомитьте изменения (git commit -am 'Добавил новую фичу')

Запушьте ветку (git push origin feature/новая-фича)

Создайте Pull Request

Правила контрибуции
✅ Следуйте PEP 8

✅ Добавляйте комментарии к сложному коду

✅ Тестируйте изменения локально перед PR

✅ Обновляйте README при изменении API

❌ Не коммитьте api_key.txt

❌ Не коммитьте blockchain_v7.db

❌ Не добавляйте реальные приватные ключи или пароли

📜 Лицензия
MIT License — подробнее в файле LICENSE

text
MIT License

Copyright (c) 2024 RAMCOIN

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
🏆 Достижения
✅ Memory-hard алгоритм — защита от ASIC/FPGA

✅ Полная экосистема — нода + майнер + кошелёк

✅ Шифрование P2P — ChaCha20-Poly1305 + ECDH

✅ Anti-cheat система — проверка потоков, RAM, модификаций

✅ Prometheus метрики — мониторинг в реальном времени

✅ BIP39 мнемоника — стандартное восстановление кошелька

✅ Офлайн-транзакции — подпись без подключения к сети

✅ Автоматический failover — переключение между нодами

✅ Термозащита CPU — троттлинг при перегреве

✅ Кроссплатформенность — Windows, Linux, macOS

<div align="center">
⚡ RAMCOIN — Честный майнинг для всех! ⚡

⭐ Star |
🔱 Fork |
📥 Download |
🐛 Report Bug |
💡 Request Feature

</div> ```
