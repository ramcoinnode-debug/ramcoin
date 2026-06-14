markdown
# RAMCOIN v10.2.1

![Version](https://img.shields.io/badge/version-10.2.1-blue)
![Protocol](https://img.shields.io/badge/protocol-2-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

Децентрализованная криптовалюта с защищённой P2P-сетью и алгоритмом Ramhash v7 (Memory-hard PoW).

## 🚀 Особенности

- **Алгоритм:** Ramhash v7 (Memory-hard, ASIC-resistant)
- **Шифрование P2P:** ChaCha20-Poly1305 + ECDH
- **Защита от атак:** Eclipse, Sybil, DDoS
- **Градуированная репутационная система** для seed-нод
- **Квантово-устойчивое резервирование**

## 📊 Параметры

| Параметр | Значение |
|----------|----------|
| Ticker | RAM |
| Блок | 30 секунд |
| Награда | 10 RAM |
| Халвинг | 876 000 блоков |
| Max supply | 21 000 000 RAM |
| Комиссия | 0.001 RAM |
| Порт P2P | 8333 |
| Порт API | 5000 |

## 📦 Компоненты

- `ramcoin_full2.py` — Нода (блокчейн + P2P + API)
- `miner2.py` — Майнер (SOLO + POOL)
- `wallet.py` — Кошелёк (AES-256-GCM)

## 🔧 Установка

```bash
pip install aiohttp lz4 cryptography psutil pycryptodome prometheus_client
🖥️ Запуск
Нода:

bash
python ramcoin_full2.py
Майнер:

bash
python miner2.py
Кошелёк:

bash
python wallet.py
🌐 API
Endpoint	Описание
/chain	Блокчейн
/stats	Статистика
/health	Здоровье
/coininfo	Информация о монете
/pool/template	Шаблон для пула
/pool/share	Отправка шары
/tx	Отправка транзакции
/address/{addr}	Баланс адреса
🔗 Ссылки
Website: https://ramcoin.network

Discord: https://discord.gg/ramcoin

Twitter: https://twitter.com/ramcoin
