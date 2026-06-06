<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAMCOIN — Революция CPU-майнинга! Майни на своём компьютере!</title>
    <meta name="description" content="RAMCOIN — первая truly децентрализованная криптовалюта с честным CPU-майнингом. Никаких ASIC, никаких ферм. Только твой процессор!">
    <meta property="og:title" content="RAMCOIN — Честный майнинг для каждого!">
    <meta property="og:description" content="Запусти майнер и зарабатывай RAM прямо сейчас!">
    <style>
        :root {
            --bg: #030712; --bg-card: #0f172a; --border: #1e293b;
            --blue: #38bdf8; --green: #10b981; --gold: #fbbf24; --red: #ef4444;
            --text: #f1f5f9; --text2: #94a3b8; --purple: #a78bfa; --pink: #f472b6;
            --gradient: linear-gradient(135deg, #38bdf8, #a78bfa, #f472b6);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; overflow-x: hidden; }
        
        /* АНИМИРОВАННЫЙ ФОН */
        body::before {
            content: ''; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: radial-gradient(ellipse at 20% 50%, rgba(56,189,248,0.08) 0%, transparent 50%),
                        radial-gradient(ellipse at 80% 20%, rgba(168,120,250,0.08) 0%, transparent 50%),
                        radial-gradient(ellipse at 50% 80%, rgba(244,114,182,0.05) 0%, transparent 50%);
            z-index: -1; pointer-events: none;
        }
        
        nav { background: rgba(3,7,18,0.95); backdrop-filter: blur(20px); border-bottom: 1px solid var(--border); 
              padding: 15px 25px; display: flex; justify-content: space-between; align-items: center; 
              flex-wrap: wrap; gap: 10px; position: sticky; top: 0; z-index: 100; }
        nav .logo { font-size: 1.8em; font-weight: 900; background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        nav .badge { background: rgba(16,185,129,0.2); color: var(--green); padding: 6px 14px; border-radius: 50px; 
                    font-weight: 700; font-size: 0.8em; border: 1px solid rgba(16,185,129,0.3); animation: pulse 2s infinite; }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.6; } }
        
        .container { max-width: 1000px; margin: 0 auto; padding: 20px; }
        
        /* HERO — ГЛАВНЫЙ БАННЕР */
        .hero { text-align: center; padding: 50px 20px 40px; position: relative; }
        .hero-badge { display: inline-block; background: rgba(239,68,68,0.15); color: var(--red); 
                     border: 2px solid rgba(239,68,68,0.5); padding: 10px 28px; border-radius: 50px; 
                     font-weight: 900; font-size: 1em; margin: 20px 0; text-transform: uppercase; 
                     letter-spacing: 2px; animation: shake 0.5s infinite; }
        @keyframes shake { 0%,100% { transform:translateX(0); } 25% { transform:translateX(-3px); } 75% { transform:translateX(3px); } }
        .hero h1 { font-size: 4em; font-weight: 900; line-height: 1.1; 
                  background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                  text-shadow: 0 0 80px rgba(56,189,248,0.3); }
        .hero .subtitle { color: var(--text); font-size: 1.4em; margin: 15px 0; font-weight: 600; }
        .hero .desc { color: var(--text2); font-size: 1.1em; max-width: 600px; margin: 0 auto; }
        
        /* СТАТИСТИКА */
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin: 20px 0; }
        .stat-item { background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; padding: 22px 15px; text-align: center; transition: all 0.3s; }
        .stat-item:hover { border-color: var(--blue); transform: translateY(-4px); box-shadow: 0 8px 25px rgba(56,189,248,0.15); }
        .stat-item .icon { font-size: 2em; margin-bottom: 8px; }
        .stat-item .value { font-size: 1.4em; font-weight: 900; background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .stat-item .label { color: var(--text2); font-size: 0.75em; margin-top: 5px; text-transform: uppercase; letter-spacing: 1px; }
        
        .card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 20px; padding: 28px; margin: 16px 0; 
               transition: all 0.3s; position: relative; overflow: hidden; }
        .card::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 3px; 
                       background: var(--gradient); opacity: 0; transition: opacity 0.3s; }
        .card:hover::before { opacity: 1; }
        h2 { background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
            margin-bottom: 18px; font-size: 1.5em; font-weight: 900; }
        h3 { margin: 12px 0; font-size: 1.1em; color: var(--blue); }
        
        /* КНОПКИ */
        .btn-group { display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; margin: 10px 0; }
        .btn { display: inline-block; padding: 16px 32px; border-radius: 14px; font-weight: 800; text-decoration: none; 
               border: none; cursor: pointer; font-size: 1em; text-align: center; transition: all 0.3s; 
               text-transform: uppercase; letter-spacing: 1px; position: relative; overflow: hidden; }
        .btn::after { content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; 
                     background: rgba(255,255,255,0.1); transform: rotate(45deg); transition: all 0.5s; }
        .btn:hover::after { left: 100%; }
        .btn:hover { transform: translateY(-3px); box-shadow: 0 10px 30px rgba(0,0,0,0.4); }
        .btn-primary { background: #0284c7; color: white; font-size: 1.2em; }
        .btn-green { background: #059669; color: white; font-size: 1.2em; }
        .btn-purple { background: #7c3aed; color: white; font-size: 1.2em; }
        .btn-gold { background: #b45309; color: white; }
        .btn-big { font-size: 1.4em; padding: 20px 40px; width: 100%; }
        
        /* ШАГИ */
        .steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
        .step { text-align: center; padding: 28px 20px; background: rgba(56,189,248,0.03); border-radius: 18px; 
               border: 1px solid var(--border); transition: all 0.3s; }
        .step:hover { border-color: var(--blue); transform: translateY(-4px); }
        .step .num { font-size: 3em; font-weight: 900; background: var(--gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .step p { margin: 6px 0; font-size: 1em; font-weight: 600; }
        .step .desc { color: var(--text2); font-size: 0.85em; }
        
        .specs { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.95em; }
        .specs .spec-label { color: var(--text2); }
        .specs .spec-value { font-weight: 700; color: var(--blue); }
        
        .social { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin: 20px 0; }
        .social a { background: var(--bg-card); border: 2px solid var(--border); padding: 12px 22px; 
                   border-radius: 12px; color: var(--text); text-decoration: none; font-weight: 700; 
                   font-size: 0.9em; transition: all 0.3s; }
        .social a:hover { border-color: var(--blue); color: var(--blue); transform: translateY(-2px); }
        
        .footer { text-align: center; color: var(--text2); font-size: 0.8em; padding: 30px; border-top: 1px solid var(--border); margin-top: 20px; }
        .footer a { color: var(--blue); text-decoration: none; }
        
        .warning-box { background: rgba(251,191,36,0.1); border: 2px solid rgba(251,191,36,0.4); 
                      padding: 16px; border-radius: 14px; margin: 14px 0; font-size: 0.9em; text-align: center; }
        .success-box { background: rgba(16,185,129,0.1); border: 2px solid rgba(16,185,129,0.4); 
                      padding: 16px; border-radius: 14px; margin: 14px 0; font-size: 0.95em; text-align: center; }
        
        .countdown { font-size: 2em; font-weight: 900; color: var(--red); }
        .highlight { background: rgba(251,191,36,0.2); padding: 2px 8px; border-radius: 6px; font-weight: 700; }
        
        @media (max-width: 600px) {
            .hero h1 { font-size: 2.5em; }
            .btn { width: 100%; padding: 14px 20px; }
            .specs { grid-template-columns: 1fr; }
            .btn-group { flex-direction: column; }
        }
    </style>
</head>
<body>
    <nav>
        <span class="logo">⚡ RAMCOIN</span>
        <span class="badge">● LIVE — ИДЁТ МАЙНИНГ!</span>
        <a href="https://t.me/ramcoin_pow" class="btn btn-primary" style="padding:10px 20px;font-size:0.85em;">💬 Telegram</a>
    </nav>
    
    <div class="container">
        <!-- HERO -->
        <div class="hero">
            <span class="hero-badge">🔥 ЗАПУСК СЕГОДНЯ! ПРИСОЕДИНЯЙСЯ!</span>
            <h1>RAMCOIN</h1>
            <p class="subtitle">Первая truly честная криптовалюта</p>
            <p class="desc">Никаких ASIC. Никаких ферм. Никаких привилегий.<br>
            <strong>Только твой процессор. Только честный майнинг.</strong></p>
            <div style="margin-top:25px;">
                <a href="#download" class="btn btn-big btn-primary">⚡ СКАЧАТЬ И МАЙНИТЬ ПРЯМО СЕЙЧАС!</a>
            </div>
        </div>

        <!-- КЛЮЧЕВЫЕ ЦИФРЫ -->
        <div class="stats-grid">
            <div class="stat-item">
                <div class="icon">🔥</div>
                <div class="value">15,500+</div>
                <div class="label">Блоков добыто</div>
            </div>
            <div class="stat-item">
                <div class="icon">💰</div>
                <div class="value">155,000+</div>
                <div class="label">RAM эмитировано</div>
            </div>
            <div class="stat-item">
                <div class="icon">⏱️</div>
                <div class="value">~30 сек</div>
                <div class="label">Время блока</div>
            </div>
            <div class="stat-item">
                <div class="icon">👥</div>
                <div class="value">3+</div>
                <div class="label">Майнера в сети</div>
            </div>
            <div class="stat-item">
                <div class="icon">💎</div>
                <div class="value">10 RAM</div>
                <div class="label">Награда за блок</div>
            </div>
            <div class="stat-item">
                <div class="icon">🛡️</div>
                <div class="value">CPU ONLY</div>
                <div class="label">ASIC не пройдут!</div>
            </div>
        </div>

        <!-- СКАЧАТЬ -->
        <div class="card" id="download" style="text-align:center;">
            <h2>📥 НАЧНИ МАЙНИТЬ ПРЯМО СЕЙЧАС!</h2>
            <p style="color:var(--text2); margin:10px 0; font-size:1.1em;">Скачал → Запустил → Зарабатываешь!</p>
            
            <div class="btn-group">
                <a href="https://github.com/ramcoinnode-debug/ramcoin/releases/latest" class="btn btn-purple">💼 Кошелёк</a>
                <a href="https://github.com/ramcoinnode-debug/ramcoin/releases/latest" class="btn btn-green">⛏️ Майнер</a>
                <a href="https://github.com/ramcoinnode-debug/ramcoin/releases/latest" class="btn btn-primary">🌐 Нода</a>
            </div>
            
            <div class="warning-box">
                ⚠️ Windows Defender может показать предупреждение — это нормально!<br>
                Нажми <strong>"Подробнее"</strong> → <strong>"Выполнить в любом случае"</strong>
            </div>
            <div class="success-box">
                ✅ <strong>Уже работает!</strong> Первые майнеры уже добывают монеты. Присоединяйся!
            </div>
        </div>

        <!-- КАК НАЧАТЬ -->
        <div class="card">
            <h2>🚀 Как начать зарабатывать за 2 минуты</h2>
            <div class="steps">
                <div class="step">
                    <div class="num">1</div>
                    <p><strong>Скачай Кошелёк</strong></p>
                    <p class="desc">Создай адрес RAM — это твой счёт для получения монет</p>
                </div>
                <div class="step">
                    <div class="num">2</div>
                    <p><strong>Скачай Майнер</strong></p>
                    <p class="desc">Выбери SOLO (10 RAM/блок) или POOL (доля от блока)</p>
                </div>
                <div class="step">
                    <div class="num">3</div>
                    <p><strong>Запусти и зарабатывай!</strong></p>
                    <p class="desc">Майнер сам подключится к сети. Просто жди блоки!</p>
                </div>
            </div>
            <div class="success-box" style="margin-top:20px;">
                🎯 <strong>Твой процессор будет приносить тебе монеты круглосуточно!</strong>
            </div>
        </div>

        <!-- ХАРАКТЕРИСТИКИ -->
        <div class="card">
            <h2>⚙️ Технические характеристики</h2>
            <div class="specs">
                <p class="spec-label">⚡ Алгоритм:</p>
                <p class="spec-value">RAM-Hash Memory-Hard (только CPU!)</p>
                
                <p class="spec-label">💎 Максимальная эмиссия:</p>
                <p class="spec-value">17 520 000 RAM</p>
                
                <p class="spec-label">⏱️ Время блока:</p>
                <p class="spec-value">~30 секунд (адаптивная сложность)</p>
                
                <p class="spec-label">🔥 Дефляция:</p>
                <p class="spec-value">1% сжигается КАЖДЫЙ БЛОК!</p>
                
                <p class="spec-label">🔒 Подписи:</p>
                <p class="spec-value">ECDSA secp256k1 + SHA256</p>
                
                <p class="spec-label">🛡️ Защита от ASIC:</p>
                <p class="spec-value">512KB - 4MB scratchpad (динамический)</p>
                
                <p class="spec-label">🌐 Сеть:</p>
                <p class="spec-value">Полностью P2P, авто-подключение</p>
                
                <p class="spec-label">💰 Халвинг:</p>
                <p class="spec-value">Каждые 876,000 блоков (~30 лет)</p>
                
                <p class="spec-label">🧵 Потоки:</p>
                <p class="spec-value">До 4 потоков на майнер (честно для всех)</p>
            </div>
        </div>

        <!-- ПОЧЕМУ RAMCOIN -->
        <div class="card">
            <h2>💡 Почему RAMCOIN — это революция?</h2>
            <div style="display:grid;gap:14px;font-size:1.05em;">
                <p>🔥 <strong>Только CPU майнинг</strong> — никакие видеокарты, фермы или ASIC не получат преимущества. Твой домашний компьютер равен серверу!</p>
                <p>🤖 <strong>Автоматическая сеть</strong> — запустил майнер и он САМ подключился к работающей сети. Никаких настроек!</p>
                <p>💰 <strong>Сжигание монет</strong> — каждый блок сжигает 1% награды. Монет становится меньше — цена растёт!</p>
                <p>🎯 <strong>Умная сложность</strong> — адаптируется каждый блок. Хоть 1 майнер, хоть 1000 — блоки идут стабильно.</p>
                <p>🏊 <strong>Встроенный пул</strong> — хочешь стабильный доход? Выбери POOL и получай долю с каждого блока.</p>
                <p>🔓 <strong>Полностью открытый код</strong> — всё на GitHub. Никаких скрытых механизмов.</p>
                <p>🌍 <strong>Децентрализация</strong> — нет главного сервера. Сеть живёт пока живёт хотя бы одна нода.</p>
            </div>
        </div>

        <!-- ПРИСОЕДИНЯЙСЯ -->
        <div class="card" style="text-align:center;">
            <h2>🔥 ПРИСОЕДИНЯЙСЯ К РЕВОЛЮЦИИ!</h2>
            <p style="font-size:1.2em; margin:10px 0;">Первые майнеры уже зарабатывают. Не упусти момент!</p>
            <a href="#download" class="btn btn-big btn-primary" style="display:inline-block;width:auto;">⚡ НАЧАТЬ МАЙНИТЬ СЕЙЧАС!</a>
            <div class="social" style="margin-top:20px;">
                <a href="https://t.me/ramcoin_pow">💬 Telegram</a>
                <a href="https://github.com/ramcoinnode-debug/ramcoin">📦 GitHub</a>
                <a href="https://rutube.ru/channel/38441251/">🎬 Rutube</a>
                <a href="https://www.twitch.tv/ram_coin">🎮 Twitch</a>
                <a href="https://kick.com/ram_coin">🟢 Kick</a>
            </div>
        </div>

        <div class="footer">
            <p>🌐 Основные ноды: <strong>90.188.115.169:5000</strong> | <strong>90.188.108.252:5000</strong></p>
            <p>RAMCOIN v10.2.0 — P2P Blockchain Network</p>
            <p>© 2026 <a href="https://t.me/ramcoin_pow">RAMCOIN Community</a> — Все права защищены</p>
            <p style="margin-top:10px;font-size:0.7em;">Честный майнинг для каждого. Никакой элиты. Только сообщество.</p>
        </div>
    </div>
</body>
</html>
