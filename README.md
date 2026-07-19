markdown
# 🐏 RAMCOIN v1.0.0 — Genesis Edition

**CPU-only mining. No ASIC. No GPU. Fair launch.**

![RAMCOIN](ramcoin.png)

Memory-hard cryptocurrency with community governance, staking, and DAO.

---

## 📥 Download

👉 **[Latest Release](https://github.com/ramcoinnode-debug/ramcoin/releases/latest)**

| File | Description |
|------|-------------|
| `Wallet.exe` | Create/restore wallet, send/receive RAM |
| `MinerPOOL.exe` | Pool miner — stable shares, no private key needed |
| `MinerSOLO.exe` | Solo miner — full block reward, requires private key |
| `Web.exe` | Local explorer dashboard |

---

## ⚡ Quick Start

1. **Download** `RAMCOIN_v1.0.0.zip` from [Releases](https://github.com/ramcoinnode-debug/ramcoin/releases)
2. **Unpack** to any folder
3. **Run** `Wallet.exe` — create or restore your wallet
4. **Run** `MinerPOOL.exe` — enter your RAM address and start mining
5. **Run** `Web.exe` — open `http://localhost:8080` to see blocks, stats, and chat
6. **Done!** You're mining RAMCOIN.

---

## 📊 Specifications

| Parameter | Value |
|-----------|-------|
| **Algorithm** | Ramhash v7 (Memory-hard CPU) |
| **Block time** | 30 seconds |
| **Initial reward** | 11.9 RAM |
| **Halving** | Every 4,204,800 blocks (~4 years) |
| **Min reward** | 0.01 RAM (tail emission) |
| **Max supply** | 100,000,000 RAM |
| **Mining period** | 100+ years |
| **Pool fee** | 1% |
| **Burn rate** | 1% (pool blocks) |
| **Dev fund** | 0% (community governed) |
| **Transaction fee** | 0.001 RAM |
| **Consensus** | Proof-of-Work (CPU + RAM) |
| **Security** | ChaCha20-Poly1305 + ECDSA |
| **Network** | P2P + Seed nodes + Peer exchange |

---

## 🖥️ Run Full Node (for operators)

```bash
pip install -r requirements.txt
python Node.py
Node API will be available at http://localhost:5000.

🌐 Web Explorer
bash
python Web.py
Open http://localhost:8080 in browser.

Features:

Live blockchain stats

Block explorer with search

Mining calculator

Leaderboard (top miners)

Community chat

DAO proposals & voting

Dark/Light theme

Multi-language (EN/RU)

📡 API
Base URL: http://NODE_IP:5000

Method	Endpoint	Description
GET	/health	Node status
GET	/chain	Blockchain stats + last blocks
GET	/coininfo	Coin specifications
GET	/block/{idx}	Block by index
GET	/address/{addr}	Balance + nonce
GET	/pending	Mempool transactions
GET	/top	Top accounts
GET	/pool/template	Pool mining template
GET	/pool/stats	Pool statistics
GET	/seeds	Seed nodes
GET	/network	Network info
POST	/tx	Submit transaction
POST	/mine	Submit mined block
POST	/pool/share	Submit pool share
POST	/pool/shares_batch	Batch submit shares
WS	/ws	Live block notifications
🔗 Links
🌐 Website: ramcoin.network

💬 Telegram: t.me/ramcoin

💻 GitHub: github.com/ramcoinnode-debug/ramcoin

🛠️ Build from source
bash
git clone https://github.com/ramcoinnode-debug/ramcoin.git
cd ramcoin
pip install -r requirements.txt
python Node.py
RAMCOIN — Fair mining for everyone. 🐏
