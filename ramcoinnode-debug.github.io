<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAMCOIN v11 — Parasite Protocol. Без серверов. Без блокировок.</title>
    <meta name="description" content="RAMCOIN v11 — децентрализованная криптовалюта. Без майнинга, без серверов, без белых IP. Работает через GitHub Gist.">
    <meta property="og:title" content="RAMCOIN v11 — Parasite Protocol">
    <meta property="og:description" content="Криптовалюта которая работает всегда. Без серверов, без доменов, без блокировок.">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🐏</text></svg>">
    <style>
        :root {
            --bg: #02040a; --bg-card: #0a0f1a; --border: #1a2030;
            --blue: #38bdf8; --green: #10b981; --gold: #fbbf24; --purple: #a78bfa;
            --text: #f1f5f9; --text2: #94a3b8;
            --gradient: linear-gradient(135deg, #38bdf8, #a78bfa);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; line-height: 1.6; }
        body::before {
            content: ''; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: radial-gradient(ellipse at 20% 50%, rgba(56,189,248,0.06) 0%, transparent 50%),
                        radial-gradient(ellipse at 80% 20%, rgba(168,120,250,0.06) 0%, transparent 50%);
            z-index: -1;
        }
        nav { background: rgba(2,4,10,0.95); backdrop-filter: blur(20px); border-bottom: 1px solid var(--border); 
              padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }
        nav .logo { font-size: 1.6em; font-weight: 900; background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .network-status { display: flex; align-items: center; gap: 8px; padding: 6px 14px; background: rgba(16,185,129,0.1); border-radius: 50px; border: 1px solid rgba(16,185,129,0.3); font-size: 0.75em; font-weight: 700; }
        .status-dot { width: 8px; height: 8px; background: var(--green); border-radius: 50%; animation: pulse 2s infinite; }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.6; } }
        .container { max-width: 900px; margin: 0 auto; padding: 20px; }
        .hero { text-align: center; padding: 60px 15px 40px; }
        .hero-badge { display: inline-block; background: rgba(16,185,129,0.12); color: var(--green); border: 2px solid rgba(16,185,129,0.4); padding: 10px 24px; border-radius: 50px; font-weight: 900; font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; animation: glow 2s infinite; }
        @keyframes glow { 0%,100% { box-shadow: 0 0 10px rgba(16,185,129,0.3); } 50% { box-shadow: 0 0 25px rgba(16,185,129,0.6); } }
        .hero h1 { font-size: clamp(2.5em, 8vw, 4em); font-weight: 900; background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 10px 0; }
        .hero .subtitle { font-size: clamp(1em, 3vw, 1.4em); font-weight: 600; margin: 12px 0; }
        .hero .desc { color: var(--text2); font-size: 1em; max-width: 600px; margin: 0 auto; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin: 20px 0; }
        .stat-item { background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px; padding: 20px 14px; text-align: center; transition: all 0.3s; }
        .stat-item:hover { border-color: var(--blue); transform: translateY(-4px); }
        .stat-item .icon { font-size: 1.8em; margin-bottom: 8px; }
        .stat-item .value { font-size: 1.2em; font-weight: 900; background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .stat-item .label { color: var(--text2); font-size: 0.7em; margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }
        .card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 18px; padding: 28px; margin: 16px 0; }
        .card::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: var(--gradient); opacity: 0; transition: opacity 0.3s; }
        .card:hover::before { opacity: 1; }
        .card { position: relative; overflow: hidden; }
        h2 { background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 16px; font-size: 1.3em; font-weight: 900; }
        .btn-group { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin: 12px 0; }
        .btn { display: inline-block; padding: 14px 28px; border-radius: 12px; font-weight: 800; text-decoration: none; border: none; cursor: pointer; font-size: 0.95em; text-align: center; transition: all 0.3s; text-transform: uppercase; letter-spacing: 1px; }
        .btn:hover { transform: translateY(-3px); box-shadow: 0 10px 30px rgba(0,0,0,0.4); }
        .btn-primary { background: #0284c7; color: white; font-size: 1.1em; }
        .btn-green { background: #059669; color: white; font-size: 1.1em; }
        .specs { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9em; }
        .specs .spec-label { color: var(--text2); }
        .specs .spec-value { font-weight: 700; color: var(--blue); }
        .success-box { background: rgba(16,185,129,0.08); border: 2px solid rgba(16,185,129,0.3); padding: 16px; border-radius: 12px; margin: 14px 0; text-align: center; }
        .info-box { background: rgba(56,189,248,0.08); border: 2px solid rgba(56,189,248,0.3); padding: 16px; border-radius: 12px; margin: 14px 0; }
        .steps-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; text-align: center; }
        .step-card { padding: 22px; background: rgba(56,189,248,0.04); border-radius: 14px; border: 1px solid var(--border); transition: all 0.3s; }
        .step-card:hover { border-color: var(--blue); }
        .step-number { font-size: 3em; font-weight: 900; color: var(--blue); }
        .social { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin: 18px 0; }
        .social a { background: var(--bg-card); border: 2px solid var(--border); padding: 12px 20px; border-radius: 12px; color: var(--text); text-decoration: none; font-weight: 700; font-size: 0.85em; transition: all 0.3s; }
        .social a:hover { border-color: var(--blue); color: var(--blue); }
        .footer { text-align: center; color: var(--text2); font-size: 0.8em; padding: 30px 20px; border-top: 1px solid var(--border); margin-top: 20px; }
        .footer a { color: var(--blue); text-decoration: none; }
        @media (max-width: 768px) {
            .hero h1 { font-size: 2.2em; }
            .specs { grid-template-columns: 1fr; }
            .card { padding: 20px; }
        }
    </style>
</head>
<body>
    <nav>
        <span class="logo">⚡ RAMCOIN v11</span>
        <div class="network-status">
            <span class="status-dot"></span>
            <span>● СЕТЬ РАБОТАЕТ</span>
        </div>
    </nav>
    
    <div class="container">
        <!-- HERO -->
        <div class="hero">
            <span class="hero-badge">⚡ PARASITE PROTOCOL • L5</span>
            <h1>RAMCOIN v11</h1>
            <p class="subtitle">Без серверов. Без белых IP. Без блокировок.</p>
            <p class="desc">Криптовалюта которая работает всегда.<br>Открытый код. Нулевая инфраструктура. Живая сеть.</p>
            <div style="margin-top:25px;">
                <a href="#download" class="btn btn-primary" style="font-size:1.2em;padding:18px 40px;">🚀 СКАЧАТЬ НОДУ</a>
            </div>
        </div>

        <!-- СТАТИСТИКА -->
        <div class="stats-grid">
            <div class="stat-item"><div class="icon">🔗</div><div class="value" id="stat-height">...</div><div class="label">БЛОКОВ</div></div>
            <div class="stat-item"><div class="icon">💰</div><div class="value" id="stat-supply">...</div><div class="label">RAM В СЕТИ</div></div>
            <div class="stat-item"><div class="icon">⏱️</div><div class="value">20 сек</div><div class="label">ВРЕМЯ БЛОКА</div></div>
            <div class="stat-item"><div class="icon">💎</div><div class="value">10 RAM</div><div class="label">НАГРАДА</div></div>
            <div class="stat-item"><div class="icon">🔥</div><div class="value">~17.5M</div><div class="label">МАКС. ЭМИССИЯ</div></div>
            <div class="stat-item"><div class="icon">🟢</div><div class="value" style="color:var(--green);">ОНЛАЙН</div><div class="label">СЕТЬ</div></div>
        </div>

        <!-- ЧТО ТАКОЕ -->
        <div class="card">
            <h2>🦠 PARASITE PROTOCOL — ЧТО ЭТО</h2>
            <p style="color:var(--text2);">RAMCOIN v11 использует GitHub Gist как транспортный слой. Никаких серверов, доменов, белых IP. Сеть живёт пока жив GitHub. Блокировки бесполезны.</p>
            <div class="info-box">
                <strong>🔒 Устойчивость к блокировкам:</strong> Трафик неотличим от обычного HTTPS. Нода общается с github.com — как миллионы разработчиков каждый день.
            </div>
            <div class="info-box">
                <strong>🌐 Всегда онлайн:</strong> Запустил ноду — она сама найдёт сеть через Gist. Без seed-нод, без настройки.
            </div>
        </div>

        <!-- КАК НАЧАТЬ -->
        <div class="card" id="download">
            <h2>🚀 КАК ЗАПУСТИТЬ НОДУ (3 ШАГА)</h2>
            <div class="steps-grid">
                <div class="step-card">
                    <div class="step-number">1</div>
                    <p><strong>Скачай</strong></p>
                    <p style="color:var(--text2);font-size:0.85em;">Скачай <code>ramcoin_v11_node.py</code> с GitHub</p>
                </div>
                <div class="step-card">
                    <div class="step-number">2</div>
                    <p><strong>Установи</strong></p>
                    <p style="color:var(--text2);font-size:0.85em;"><code>pip install aiohttp cryptography lz4</code></p>
                </div>
                <div class="step-card">
                    <div class="step-number">3</div>
                    <p><strong>Запусти</strong></p>
                    <p style="color:var(--text2);font-size:0.85em;"><code>python ramcoin_v11_node.py</code></p>
                </div>
            </div>
            <div class="success-box">
                ✅ <strong>Готово!</strong> Нода запущена. Блоки создаются каждые 20 секунд. Ты в сети.
            </div>
            <div class="btn-group">
                <a href="https://github.com/ramcoinnode-debug/ramcoin" class="btn btn-green">💻 GitHub</a>
                <a href="https://github.com/ramcoinnode-debug/ramcoin/blob/main/ramcoin_v11_wallet.py" class="btn btn-primary">👛 Кошелёк</a>
            </div>
        </div>

        <!-- ХАРАКТЕРИСТИКИ -->
        <div class="card">
            <h2>⚙️ ХАРАКТЕРИСТИКИ v11</h2>
            <div class="specs">
                <p class="spec-label">🦠 Протокол:</p><p class="spec-value">Parasite (GitHub Gist)</p>
                <p class="spec-label">⏱️ Время блока:</p><p class="spec-value">20 секунд</p>
                <p class="spec-label">💰 Награда:</p><p class="spec-value">10 RAM (халвинг каждые 876K)</p>
                <p class="spec-label">🔥 Сжигание:</p><p class="spec-value">1% с блока</p>
                <p class="spec-label">💎 Макс. эмиссия:</p><p class="spec-value">~17 500 000 RAM</p>
                <p class="spec-label">🔒 Консенсус:</p><p class="spec-value">DAG + Proof-of-Relay</p>
                <p class="spec-label">⚡ Майнинг:</p><p class="spec-value">НЕТ (не нужен)</p>
                <p class="spec-label">🌐 Транспорт:</p><p class="spec-value">GitHub API + WebRTC</p>
            </div>
        </div>

        <!-- ПРИСОЕДИНЯЙСЯ -->
        <div class="card" style="text-align:center;">
            <h2>🔥 ПРИСОЕДИНЯЙСЯ</h2>
            <p style="font-size:1.2em;">Сеть запущена. Блоки идут. Присоединяйся сейчас.</p>
            <div class="social">
                <a href="https://t.me/ramcoin_pow" target="_blank">📢 Telegram</a>
                <a href="https://github.com/ramcoinnode-debug/ramcoin" target="_blank">💻 GitHub</a>
            </div>
        </div>

        <div class="footer">
            <p>RAMCOIN v11 — Parasite Protocol</p>
            <p>© 2026 <a href="https://github.com/ramcoinnode-debug/ramcoin" target="_blank">RAMCOIN</a></p>
            <p style="margin-top:8px;font-size:0.75em;">Без серверов. Без блокировок. Всегда онлайн.</p>
        </div>
    </div>

    <script>
        async function loadStats() {
            try {
                const resp = await fetch('http://127.0.0.1:5000/stats');
                const data = await resp.json();
                document.getElementById('stat-height').textContent = (data.height || 0).toLocaleString();
                document.getElementById('stat-supply').textContent = ((data.total_supply || 0) / 100000000).toLocaleString();
            } catch(e) {
                document.getElementById('stat-height').textContent = '...';
                document.getElementById('stat-supply').textContent = '...';
            }
        }
        loadStats();
        setInterval(loadStats, 30000);
    </script>
</body>
</html>
