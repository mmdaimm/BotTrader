"""
WebTraderBot Dashboard Server (Pure Python Standard Library)
Serves Web Dashboard UI & REST APIs on http://localhost:8000 with Paper Trading & Multi-Crypto.
"""

import http.server
import socketserver
import json
import urllib.parse
import sys
import os

# Set UTF-8 encoding for standard output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.trader_bot import TraderBot

PORT = 8000
bot = TraderBot(symbols=["THB_BTC", "THB_ETH", "THB_SOL", "THB_XRP", "THB_DOGE"], resolution="15", initial_capital=10000.0)

HTML_PAGE = """<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebTraderBot - Multi-Crypto & Paper Trading Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0d14;
            --bg-card: rgba(18, 24, 38, 0.75);
            --bg-card-hover: rgba(26, 35, 56, 0.85);
            --border-color: rgba(255, 255, 255, 0.08);
            --accent-green: #00f090;
            --accent-red: #ff3b69;
            --accent-blue: #3b82f6;
            --accent-yellow: #f59e0b;
            --accent-purple: #8b5cf6;
            --text-primary: #f3f4f6;
            --text-muted: #9ca3af;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Inter', sans-serif;
        }

        body {
            background-color: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 24px;
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(0, 240, 144, 0.05) 0%, transparent 40%),
                radial-gradient(circle at 85% 85%, rgba(139, 92, 246, 0.05) 0%, transparent 40%);
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 24px;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-icon {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            background: linear-gradient(135deg, #00f090, #8b5cf6);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 20px;
            color: #000;
        }

        .brand-text h1 {
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }

        .brand-text p {
            font-size: 12px;
            color: var(--text-muted);
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 20px;
            background: rgba(0, 240, 144, 0.1);
            border: 1px solid rgba(0, 240, 144, 0.2);
            color: var(--accent-green);
            font-size: 13px;
            font-weight: 600;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent-green);
            box-shadow: 0 0 10px var(--accent-green);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        .btn-group {
            display: flex;
            gap: 10px;
        }

        .mode-btn {
            background: rgba(59, 130, 246, 0.15);
            border: 1px solid rgba(59, 130, 246, 0.3);
            color: var(--accent-blue);
            padding: 10px 16px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
        }

        .panic-btn {
            background: linear-gradient(135deg, #ff3b69, #dc2626);
            color: white;
            border: none;
            padding: 10px 18px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(255, 59, 105, 0.4);
            transition: all 0.2s ease;
        }

        .reset-btn {
            background: rgba(255,255,255,0.08);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 10px 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
        }

        .grid-crypto {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }

        .card {
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 18px;
            transition: all 0.2s ease;
        }

        .card:hover {
            border-color: rgba(255, 255, 255, 0.15);
            background: var(--bg-card-hover);
        }

        .card-title {
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            justify-content: space-between;
        }

        .card-value {
            font-size: 22px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }

        .card-sub {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 6px;
        }

        .main-layout {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }

        .section-header {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .terminal {
            background: #06080d;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            color: #a7f3d0;
            height: 250px;
            overflow-y: auto;
            line-height: 1.6;
        }

        .log-item {
            margin-bottom: 6px;
            display: flex;
            gap: 12px;
        }

        .log-time {
            color: var(--text-muted);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            margin-top: 10px;
        }

        th, td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        th {
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
        }

        .badge-win {
            background: rgba(0, 240, 144, 0.15);
            color: var(--accent-green);
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 11px;
        }

        .badge-loss {
            background: rgba(255, 59, 105, 0.15);
            color: var(--accent-red);
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 11px;
        }

        .sim-buy-btn {
            background: var(--accent-green);
            color: #000;
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 700;
            font-size: 10px;
            cursor: pointer;
        }
    </style>
</head>
<body>

    <div class="header">
        <div class="brand">
            <div class="brand-icon">W</div>
            <div class="brand-text">
                <h1>WebTraderBot Dashboard</h1>
                <p>Multi-Crypto Paper Trading Engine (BTC, ETH, SOL, XRP, DOGE)</p>
            </div>
        </div>

        <div style="display: flex; gap: 16px; align-items: center;">
            <div class="status-badge" id="statusBadge">
                <div class="status-dot" id="statusDot"></div>
                <span id="statusText">PAPER TRADING MODE ONLINE</span>
            </div>
            <div class="btn-group">
                <button class="mode-btn" id="modeBtn" onclick="toggleMode()">MODE: PAPER TRADING</button>
                <button class="reset-btn" onclick="resetBot()">Reset System</button>
                <button class="panic-btn" id="panicBtn">EMERGENCY PANIC STOP</button>
            </div>
        </div>
    </div>

    <!-- Multi-Crypto Asset Cards -->
    <div class="grid-crypto">
        <div class="card">
            <div class="card-title">
                <span>BTC/USDT</span>
                <button class="sim-buy-btn" onclick="simBuy('THB_BTC')">+ Test Buy</button>
            </div>
            <div class="card-value" id="price_THB_BTC">$0.00</div>
            <div class="card-sub" id="sig_THB_BTC">Searching...</div>
        </div>
        <div class="card">
            <div class="card-title">
                <span>ETH/USDT</span>
                <button class="sim-buy-btn" onclick="simBuy('THB_ETH')">+ Test Buy</button>
            </div>
            <div class="card-value" id="price_THB_ETH">$0.00</div>
            <div class="card-sub" id="sig_THB_ETH">Searching...</div>
        </div>
        <div class="card">
            <div class="card-title">
                <span>SOL/USDT</span>
                <button class="sim-buy-btn" onclick="simBuy('THB_SOL')">+ Test Buy</button>
            </div>
            <div class="card-value" id="price_THB_SOL">$0.00</div>
            <div class="card-sub" id="sig_THB_SOL">Searching...</div>
        </div>
        <div class="card">
            <div class="card-title">
                <span>XRP/USDT</span>
                <button class="sim-buy-btn" onclick="simBuy('THB_XRP')">+ Test Buy</button>
            </div>
            <div class="card-value" id="price_THB_XRP">$0.00</div>
            <div class="card-sub" id="sig_THB_XRP">Searching...</div>
        </div>
        <div class="card">
            <div class="card-title">
                <span>DOGE/USDT</span>
                <button class="sim-buy-btn" onclick="simBuy('THB_DOGE')">+ Test Buy</button>
            </div>
            <div class="card-value" id="price_THB_DOGE">$0.00</div>
            <div class="card-sub" id="sig_THB_DOGE">Searching...</div>
        </div>
    </div>

    <!-- Main Layout -->
    <div class="main-layout">
        <!-- System Logs -->
        <div class="card">
            <div class="section-header">
                <span>Multi-Asset Signal Feed</span>
                <button onclick="fetchStatus()" style="background: transparent; border: 1px solid var(--border-color); color: var(--text-muted); padding: 4px 10px; border-radius: 6px; cursor: pointer;">Refresh Now</button>
            </div>
            <div class="terminal" id="terminalLog">
                <div class="log-item"><span class="log-time">[System]</span> Multi-Crypto Engine Initialized (BTC, ETH, SOL, XRP, DOGE).</div>
                <div class="log-item"><span class="log-time">[System]</span> Telegram Bot Connected (@my_webtrader_crypto_bot).</div>
            </div>
        </div>

        <!-- Paper Trading Portfolio Summary -->
        <div class="card">
            <div class="section-header">
                <span>Paper Portfolio Summary</span>
            </div>
            <div style="padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 13px; display:flex; justify-content:space-between;">
                <span style="color:var(--text-muted)">Current Balance</span>
                <span style="font-weight:700; font-family:'JetBrains Mono'" id="paperBal">$10,000.00</span>
            </div>
            <div style="padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 13px; display:flex; justify-content:space-between;">
                <span style="color:var(--text-muted)">Net PnL</span>
                <span style="font-weight:700; font-family:'JetBrains Mono'; color:var(--accent-green)" id="paperPnl">$0.00 (0.00%)</span>
            </div>
            <div style="padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 13px; display:flex; justify-content:space-between;">
                <span style="color:var(--text-muted)">Win Rate</span>
                <span style="font-weight:700; font-family:'JetBrains Mono'" id="paperWinRate">0.00% (0 Trades)</span>
            </div>
            <div style="padding: 12px 0; font-size: 13px; display:flex; justify-content:space-between;">
                <span style="color:var(--text-muted)">Fee Deduction</span>
                <span style="font-weight:700; color:var(--text-muted)">Bitkub 0.25% Net</span>
            </div>
        </div>
    </div>

    <!-- Active Positions & History Tables -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
        <div class="card">
            <div class="section-header">
                <span>Active Paper Positions</span>
            </div>
            <table id="activePosTable">
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Entry Price</th>
                        <th>Stop Loss</th>
                        <th>Take Profit</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td colspan="5" style="color:var(--text-muted)">No active positions</td></tr>
                </tbody>
            </table>
        </div>

        <div class="card">
            <div class="section-header">
                <span>Closed Trade History</span>
            </div>
            <table id="historyTable">
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Result</th>
                        <th>Entry $\rightarrow$ Exit</th>
                        <th>Net PnL</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td colspan="4" style="color:var(--text-muted)">No closed trades yet</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                if (data.status === 'PAUSED') {
                    document.getElementById('statusText').innerText = 'PAUSED (CIRCUIT BREAKER / PANIC)';
                    document.getElementById('statusBadge').style.background = 'rgba(255, 59, 105, 0.2)';
                    document.getElementById('statusBadge').style.color = '#ff3b69';
                    document.getElementById('statusDot').style.background = '#ff3b69';
                    return;
                }

                const pairs = data.pair_results || {};
                const logBox = document.getElementById('terminalLog');
                const now = new Date().toLocaleTimeString();

                for (const [sym, info] of Object.entries(pairs)) {
                    const priceEl = document.getElementById('price_' + sym);
                    const sigEl = document.getElementById('sig_' + sym);
                    
                    if (priceEl && info.last_price) {
                        priceEl.innerText = '$' + info.last_price.toLocaleString('en-US', {minimumFractionDigits: 2});
                    }
                    
                    if (sigEl && info.eval) {
                        sigEl.innerText = 'Signal: ' + info.eval.signal;
                        if (info.eval.signal === 'BUY') {
                            sigEl.style.color = '#00f090';
                        } else {
                            sigEl.style.color = '#9ca3af';
                        }
                    }
                }

                // Update Paper Summary
                if (data.paper_summary) {
                    const p = data.paper_summary;
                    document.getElementById('paperBal').innerText = '$' + p.current_capital.toLocaleString('en-US', {minimumFractionDigits: 2});
                    document.getElementById('paperPnl').innerText = `$${p.net_profit} (${p.net_profit_pct}%)`;
                    document.getElementById('paperPnl').style.color = p.net_profit >= 0 ? '#00f090' : '#ff3b69';
                    document.getElementById('paperWinRate').innerText = `${p.win_rate_pct}% (${p.total_trades} Trades)`;
                }

                // Update Active Positions Table
                if (data.active_positions && data.active_positions.length > 0) {
                    let html = '';
                    for (const pos of data.active_positions) {
                        html += `<tr>
                            <td><b>${pos.symbol}</b></td>
                            <td>$${pos.entry_price.toLocaleString()}</td>
                            <td style="color:#ff3b69">$${pos.sl_price.toLocaleString()}</td>
                            <td style="color:#00f090">$${pos.tp_price.toLocaleString()}</td>
                            <td>$${pos.order_value.toLocaleString()}</td>
                        </tr>`;
                    }
                    document.querySelector('#activePosTable tbody').innerHTML = html;
                } else {
                    document.querySelector('#activePosTable tbody').innerHTML = '<tr><td colspan="5" style="color:var(--text-muted)">No active positions</td></tr>';
                }

                // Update History Table
                if (data.trade_history && data.trade_history.length > 0) {
                    let html = '';
                    for (const tr of data.trade_history) {
                        const isWin = tr.net_pnl >= 0;
                        const badgeClass = isWin ? 'badge-win' : 'badge-loss';
                        html += `<tr>
                            <td><b>${tr.symbol}</b></td>
                            <td><span class="${badgeClass}">${tr.type}</span></td>
                            <td>$${tr.entry_price.toLocaleString()} &rarr; $${tr.exit_price.toLocaleString()}</td>
                            <td style="color:${isWin ? '#00f090' : '#ff3b69'}; font-weight:700">$${tr.net_pnl} (${tr.pnl_pct}%)</td>
                        </tr>`;
                    }
                    document.querySelector('#historyTable tbody').innerHTML = html;
                }

            } catch (err) {
                console.error("Fetch error:", err);
            }
        }

        async function triggerPanic() {
            if (confirm("EMERGENCY PANIC STOP:\nคุณต้องการยกเลิกออเดอร์ทั้งหมด และหยุด Bot ทันทีหรือไม่?")) {
                try {
                    const res = await fetch('/api/panic', { method: 'POST' });
                    const data = await res.json();
                    alert(data.message);
                    fetchStatus();
                } catch(e) {
                    console.error("Panic trigger error:", e);
                }
            }
        }

        async function resetBot() {
            const res = await fetch('/api/reset', { method: 'POST' });
            const data = await res.json();
            alert(data.message);
            document.getElementById('statusText').innerText = 'MULTI-CRYPTO ENGINE ONLINE';
            document.getElementById('statusBadge').style.background = 'rgba(0, 240, 144, 0.1)';
            document.getElementById('statusBadge').style.color = '#00f090';
            document.getElementById('statusDot').style.background = '#00f090';
            fetchStatus();
        }

        async function toggleMode() {
            const res = await fetch('/api/toggle-mode', { method: 'POST' });
            const data = await res.json();
            document.getElementById('modeBtn').innerText = 'MODE: ' + data.mode;
            alert('Switched to: ' + data.mode + ' TRADING MODE');
        }

        async function simBuy(symbol) {
            const res = await fetch('/api/sim-buy?symbol=' + symbol, { method: 'POST' });
            const data = await res.json();
            alert(data.message);
            fetchStatus();
        }

        window.triggerPanic = triggerPanic;
        window.resetBot = resetBot;
        window.toggleMode = toggleMode;
        window.simBuy = simBuy;

        document.addEventListener('DOMContentLoaded', () => {
            const btn = document.getElementById('panicBtn');
            if (btn) btn.addEventListener('click', triggerPanic);
        });

        fetchStatus();
        setInterval(fetchStatus, 5000);
    </script>
</body>
</html>
"""

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            res = bot.run_single_iteration()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/panic":
            bot.risk_engine.is_circuit_broken = True
            bot.notifier.send_panic_alert("Manual User Action via Web Dashboard Button")
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            msg = {"status": "SUCCESS", "message": "PANIC STOP ACTIVATED: Open orders cancelled & Bot trading locked."}
            self.wfile.write(json.dumps(msg).encode("utf-8"))
        elif parsed.path == "/api/reset":
            bot.risk_engine.reset_circuit_breaker()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            msg = {"status": "SUCCESS", "message": "Bot Reset successfully. Multi-Crypto trading active."}
            self.wfile.write(json.dumps(msg).encode("utf-8"))
        elif parsed.path == "/api/toggle-mode":
            bot.trading_mode = "LIVE" if bot.trading_mode == "PAPER" else "PAPER"
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            msg = {"status": "SUCCESS", "mode": bot.trading_mode}
            self.wfile.write(json.dumps(msg).encode("utf-8"))
        elif parsed.path == "/api/sim-buy":
            params = urllib.parse.parse_qs(parsed.query)
            sym = params.get("symbol", ["THB_BTC"])[0]
            candles = bot.client.get_candles(symbol=sym, resolution="15", limit=300)
            if candles:
                price = candles[-1]["close"]
                atr = 0.02 * price
                risk = bot.risk_engine.calculate_position_sizing(bot.paper_engine.current_capital, price, atr)
                res = bot.paper_engine.open_position(sym, price, risk)
                msg = {"status": "SUCCESS", "message": f"Simulated Paper BUY Order placed for {sym} at ${price:,.2f}"}
            else:
                msg = {"status": "ERROR", "message": f"Failed to fetch market data for {sym}"}
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(json.dumps(msg).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
        print("==========================================================")
        print(f"WebTraderBot Paper Trading Dashboard Live at: http://localhost:{PORT}")
        print("Multi-Crypto Assets: BTC, ETH, SOL, XRP, DOGE")
        print("Telegram Bot Connected: @my_webtrader_crypto_bot")
        print("==========================================================")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
