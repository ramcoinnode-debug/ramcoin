# RAMCOIN (RAM)

**Честный блокчейн с CPU-майнингом. Без ASIC, без пулов, только домашний ПК.**

*A fair blockchain with CPU mining. No ASICs, no pools, home PC only.*

---

## Текущая версия: v7.0.3

---

## Возможности

- 🖥️ CPU-only майнинг — любой ПК с 4 ГБ ОЗУ
- 🔒 Memory-Hard PoW — 4 МБ scratchpad, защита от ASIC и GPU
- 🛡️ Анти-сервер — штраф 75% для Xeon, EPYC, Threadripper
- ⚡ Соло-майнинг — нашёл блок, забрал всё (100%)
- 🤝 Пул-майнинг — стабильный доход (98% майнерам, 1% dev, 1% сжигание)
- 🔥 Сжигание — 1% с каждого блока пула
- 💰 Честный старт — 0 премайна, 0 ICO, 0 инвесторов
- 📊 17.5M монет — эмиссия на 30 лет
- 💸 Комиссия 0.001 RAM

---

## Быстрый старт

```bash
pip install -r requirements.txt
python node.py    # Запуск ноды
python miner.py   # 1 = SOLO, 2 = POOL
python wallet.py  # Кошелёк
Файлы
Файл	Описание
node.py	Нода v7.0.3
miner.py	Майнер v7.0.3 (соло + пул)
wallet.py	Кошелёк v7.0.3
index.html	Сайт
blockchain_v7.db	Полная история блокчейна
RamcoinMiner.exe	Майнер для Windows
RamcoinWallet.exe	Кошелёк для Windows
Экономика
Режим	Майнер	Dev	Сжигание
СОЛО	100%	0%	0%
ПУЛ	98%	1%	1%
Статистика сети
Блоков добыто: 14 900+

Аптайм ноды: 200+ часов

Rejected блоков: 0

Заявки на CoinMarketCap и CoinGecko поданы

Ссылки
🌐 Сайт | 📱 Telegram | ▶️ Rutube | 🎮 Twitch | 🟢 Kick

Лицензия
MIT — делай что хочешь. Это экспериментальное ПО.

© 2026 RAMCOIN Network
