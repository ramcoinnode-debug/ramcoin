# RAMCOIN v1.0.0 — Genesis Edition

CPU-mined cryptocurrency. Memory-hard algorithm. No ASIC. No GPU. Fair launch.

---

## Download

👉 [Latest Release](https://github.com/ramcoinnode-debug/ramcoin/releases/latest)

---

## Quick Start

1. Download `RAMCOIN_v1.0.0.zip` from releases
2. Unpack
3. Run `RAMCOIN_Wallet_v1.0.0.exe` — create or open wallet
4. Run `RAMCOIN_Miner_v1.0.0.exe` — enter your RAM address and start mining
5. Open `ramcoin_explorer.html` in browser to see blocks
6. Done. You're mining RAMCOIN.

---

## Specifications

| Parameter | Value |
|---|---|
| Algorithm | Ramhash v7 (Memory-hard CPU) |
| Block time | 30 seconds |
| Reward | 10 RAM |
| Halving | every 876,000 blocks (~304 days) |
| Min reward | 0.6 RAM (tail emission) |
| Max supply | ~17.5M + tail emission |
| Dev fund | 5% (transparent, in code) |
| Fee | 0.001 RAM |
| Consensus | Proof-of-Work (CPU + RAM) |
| Security | ChaCha20-Poly1305 + ECDH + ECDSA |
| Network | P2P + Peer Exchange |

---

## Links

🌐 [Website](https://ramcoinnode-debug.github.io/ramcoin)
📢 [Telegram](https://t.me/ramcoin_pow)
💻 [GitHub](https://github.com/ramcoinnode-debug/ramcoin)

---

## Run Node (for operators)

```bash
pip install -r requirements.txt
python ramcoin_node.py
