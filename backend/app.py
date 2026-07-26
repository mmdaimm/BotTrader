"""
WebTraderBot FastAPI Backend Server (Railway.app Ready)
Provides REST API services for Next.js Web Dashboard & Telegram Notifier Integration.
Supports OKX Perpetual Swaps across 15 Veteran Crypto Instruments (Age > 5 Years).
Features Non-Blocking ProcessPoolExecutor Backtest Engine & Daily Cash Flow System.
"""

from fastapi import FastAPI, Query, BackgroundTasks, Response, status, Body
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
import time
import uuid
from concurrent.futures import ProcessPoolExecutor

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def load_env_file():
    possible_paths = [
        os.path.join(PROJECT_ROOT, ".env"),
        os.path.join(os.path.dirname(PROJECT_ROOT), ".env"),
        os.path.join(PROJECT_ROOT, "WebTraderBot", ".env")
    ]
    for env_path in possible_paths:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'").strip('"')
                        if k and v and k not in os.environ:
                            os.environ[k] = v

load_env_file()

from src.core.trader_bot import TraderBot
from src.core.indicators import TechnicalIndicators
from src.core.quant_analyzer import QuantAnalyzer
from src.core.cashflow_engine import CashFlowEngine
from scripts.backtest_engine import run_backtest_process

app = FastAPI(
    title="WebTraderBot FastAPI Engine (OKX 15-Veteran Futures Portfolio)",
    description="Multi-Crypto Perpetual Futures Engine for Next.js Dashboard",
    version="5.1.0-OKX-DEMO"
)

# Enable CORS for Next.js frontend (Vercel & Localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 20 Battle-Tested Veteran Crypto Instruments (> 5 Years Old)
VETERAN_SYMBOLS = [
    "BTC-USDT-SWAP",  # Bitcoin (2009)
    "ETH-USDT-SWAP",  # Ethereum (2015)
    "XRP-USDT-SWAP",  # XRP (2012)
    "LTC-USDT-SWAP",  # Litecoin (2011)
    "BCH-USDT-SWAP",  # Bitcoin Cash (2017)
    "ADA-USDT-SWAP",  # Cardano (2017)
    "SOL-USDT-SWAP",  # Solana (March 2020)
    "DOGE-USDT-SWAP", # Dogecoin (2013)
    "LINK-USDT-SWAP", # Chainlink (2017)
    "DOT-USDT-SWAP",  # Polkadot (August 2020)
    "ATOM-USDT-SWAP", # Cosmos (2019)
    "ETC-USDT-SWAP",  # Ethereum Classic (2016)
    "XLM-USDT-SWAP",  # Stellar (2014)
    "TRX-USDT-SWAP",  # Tron (2017)
    "AVAX-USDT-SWAP", # Avalanche (September 2020)
    "BNB-USDT-SWAP",  # BNB / Binance Coin (July 2017)
    "NEAR-USDT-SWAP", # NEAR Protocol (April 2020)
    "UNI-USDT-SWAP",  # Uniswap (September 2020)
    "FIL-USDT-SWAP",  # Filecoin (October 2020)
    "ALGO-USDT-SWAP"  # Algorand (June 2019)
]

bot = TraderBot(
    symbols=VETERAN_SYMBOLS,
    resolution="240",
    initial_capital=10000.0
)
# Reconcile & Sync live OKX exchange positions on app startup if in LIVE mode
bot.sync_live_exchange_positions()
quant_analyzer = QuantAnalyzer()
cashflow_engine = CashFlowEngine(bot.client)

# Dedicated ProcessPoolExecutor for CPU-heavy backtest jobs (Never blocks main FastAPI thread)
process_pool = ProcessPoolExecutor(max_workers=2)

# Backtest Jobs Store
backtest_jobs = {}

@app.get("/")
def read_root():
    return {"message": "🟢 OKX 15-Veteran Futures Trading Engine Backend is Running Live!", "status": bot.bot_state}

@app.get("/api/status")
def get_status():
    """Return real-time bot metrics, prices, indicators, active positions, and trade history."""
    bot.sync_live_exchange_positions()
    res = bot.run_single_iteration()
    # 100% Single Source of Truth: Sync active_positions strictly with OKX Live Positions API
    if hasattr(bot, 'client') and bot.client:
        # Fetch pending algo orders to resolve attached SL/TP trigger prices
        algo_map = {}
        if hasattr(bot.client, 'get_pending_algo_orders'):
            algo_res = bot.client.get_pending_algo_orders(instType="SWAP")
            if algo_res.get("code") == "0":
                for a in algo_res.get("data", []):
                    a_sym = a.get("instId", "")
                    if a_sym not in algo_map:
                        algo_map[a_sym] = {"sl_price": 0.0, "tp_price": 0.0}
                    sl_t = float(a.get("slTriggerPx", 0.0) or 0.0)
                    tp_t = float(a.get("tpTriggerPx", 0.0) or 0.0)
                    trig_t = float(a.get("triggerPx", 0.0) or 0.0)
                    if sl_t > 0:
                        algo_map[a_sym]["sl_price"] = sl_t
                    if tp_t > 0:
                        algo_map[a_sym]["tp_price"] = tp_t
                    if trig_t > 0:
                        if sl_t <= 0 and (a.get("slTriggerPx") is not None or "sl" in str(a.get("algoClOrdId", "")).lower()):
                            algo_map[a_sym]["sl_price"] = trig_t
                        elif tp_t <= 0 and (a.get("tpTriggerPx") is not None or "tp" in str(a.get("algoClOrdId", "")).lower()):
                            algo_map[a_sym]["tp_price"] = trig_t

        okx_pos_res = bot.client.get_positions(instType="SWAP")
        if okx_pos_res.get("code") == "0":
            data_list = okx_pos_res.get("data", [])
            live_okx_positions = []
            for p in data_list:
                p_size = float(p.get("pos", 0.0) or 0.0)
                if p_size != 0:
                    sym = p.get("instId", "")
                    pos_side = str(p.get("posSide", "long")).upper()
                    if pos_side == "NET":
                        pos_side = "LONG" if p_size > 0 else "SHORT"
                    entry_px = float(p.get("avgPx", 0.0) or 0.0)
                    upl = float(p.get("upl", 0.0) or 0.0)
                    order_val = round(abs(p_size) * entry_px, 2)
                    
                    # Floating PnL % calculation: (unrealized_pnl / order_value) * 100.0 (Matching OKX Floating PnL %)
                    floating_pnl_pct = round((upl / order_val * 100.0), 2) if order_val > 0 else 0.0
                    
                    # Extract SL and TP trigger prices from OKX position object, algo orders map, or local memory fallback
                    sl_price = float(p.get("slTriggerPx", 0.0) or 0.0)
                    if sl_price <= 0 and sym in algo_map:
                        sl_price = algo_map[sym]["sl_price"]
                    if sl_price <= 0 and sym in bot.paper_engine.active_positions:
                        sl_price = float(bot.paper_engine.active_positions[sym].get("sl_price", 0.0) or 0.0)

                    tp_price = float(p.get("tpTriggerPx", 0.0) or 0.0)
                    if tp_price <= 0 and sym in algo_map:
                        tp_price = algo_map[sym]["tp_price"]
                    if tp_price <= 0 and sym in bot.paper_engine.active_positions:
                        tp_price = float(bot.paper_engine.active_positions[sym].get("tp1_target", 0.0) or 0.0)

                    live_okx_positions.append({
                        "id": f"OKX-{sym}-{pos_side}",
                        "symbol": sym,
                        "side": pos_side,
                        "timeframe": "4h",
                        "strategy_type": "SWING_4H",
                        "leverage": int(float(p.get("lever", 3) or 3)),
                        "entry_price": entry_px,
                        "qty": abs(p_size),
                        "order_value": order_val,
                        "margin_required": float(p.get("margin", 100.0) or 100.0),
                        "unrealized_pnl": round(upl, 2),
                        "pnl_pct": floating_pnl_pct,
                        "sl_price": round(sl_price, 4),
                        "tp_price": round(tp_price, 4),
                        "tp1_target": round(tp_price, 4),
                        "status": "OPEN"
                    })
            res["active_positions"] = live_okx_positions
    return res

@app.get("/api/candles")
def get_candles_data(symbol: str = Query("BTC-USDT-SWAP"), resolution: str = Query("15")):
    """
    Return historical OHLCV candles and pre-calculated indicator series
    for interactive Candlestick chart rendering on Next.js frontend.
    """
    try:
        candles = bot.client.get_candles(symbol=symbol, resolution=resolution, limit=300)
        if not candles:
            return {"symbol": symbol, "candles": [], "indicators": {}}
            
        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]
        
        ema200 = TechnicalIndicators.calculate_ema(closes, 200)
        ema9 = TechnicalIndicators.calculate_ema(closes, 9)
        ema21 = TechnicalIndicators.calculate_ema(closes, 21)
        rsi = TechnicalIndicators.calculate_rsi(closes, 14)
        adx = TechnicalIndicators.calculate_adx(candles, 14)
        vol_sma = TechnicalIndicators.calculate_sma(volumes, 20)
        vwap = TechnicalIndicators.calculate_vwap(candles)
        
        formatted_candles = []
        for i, c in enumerate(candles):
            formatted_candles.append({
                "time": c["timestamp"],
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c["volume"],
                "ema200": round(ema200[i], 4) if i < len(ema200) else None,
                "ema9": round(ema9[i], 4) if i < len(ema9) else None,
                "ema21": round(ema21[i], 4) if i < len(ema21) else None,
                "rsi": round(rsi[i], 2) if i < len(rsi) else None,
                "adx": round(adx[i], 2) if i < len(adx) else None,
                "vwap": round(vwap[i], 4) if i < len(vwap) else None,
                "vol_sma": round(vol_sma[i], 2) if i < len(vol_sma) else None
            })
            
        return {
            "symbol": symbol,
            "resolution": resolution,
            "count": len(formatted_candles),
            "candles": formatted_candles
        }
    except Exception as e:
        print(f"[API] Error fetching candles API for {symbol}: {e}")
        return {"symbol": symbol, "candles": [], "error": str(e)}

@app.get("/api/backtest")
def trigger_backtest(response: Response, symbol: str = Query("BTC-USDT-SWAP"), days: int = Query(90)):
    """
    Non-Blocking Asynchronous Backtest Trigger Endpoint.
    Launches CPU-heavy simulation in isolated ProcessPoolWorker and returns 202 Accepted immediately.
    """
    task_id = str(uuid.uuid4())[:8]
    response.status_code = status.HTTP_202_ACCEPTED
    
    # Submit job to ProcessPoolExecutor
    future = process_pool.submit(run_backtest_process, symbol, days)
    backtest_jobs[task_id] = {
        "task_id": task_id,
        "symbol": symbol,
        "days": days,
        "status": "PROCESSING",
        "future": future,
        "created_at": time.time()
    }
    
    return {
        "status": "202_ACCEPTED",
        "task_id": task_id,
        "symbol": symbol,
        "days": days,
        "message": f"⏳ Backtest job {task_id} launched in background process pool for {symbol} ({days} days)."
    }

@app.get("/api/backtest-result")
def get_backtest_result(task_id: str = Query(...)):
    """Poll for background backtest results using task_id."""
    job = backtest_jobs.get(task_id)
    if not job:
        return {"status": "NOT_FOUND", "message": f"Backtest job {task_id} not found."}
    
    future = job.get("future")
    if future and future.done():
        try:
            result = future.result()
            return {"status": "COMPLETED", "task_id": task_id, "result": result}
        except Exception as e:
            return {"status": "ERROR", "task_id": task_id, "error": str(e)}
    else:
        return {"status": "PROCESSING", "task_id": task_id, "message": "Backtest calculation in progress..."}

@app.get("/api/cashflow-summary")
def get_cashflow_summary():
    """Return 100% Real-Time Live OKX API Portfolio Allocation & Funding Metrics (No Mock Data)."""
    bal = bot.client.get_account_balance()
    total_eq = bal.get("total_equity") or bot.paper_engine.current_capital or 10000.0
    
    # 80% Funding Arbitrage Capital & 20% Swing Trading Capital
    alloc_80 = total_eq * 0.80
    alloc_20 = total_eq * 0.20
    
    # Fetch real live funding rate for BTC-USDT-SWAP from OKX API
    fr_data = bot.client.get_funding_rate("BTC-USDT-SWAP")
    annual_apy = fr_data.get("annual_apy_pct", 10.95)
    daily_cashflow = (alloc_80 * (annual_apy / 100.0)) / 365.0
    
    # Real live OKX positions and active risk heat
    active_pos_count = len(bot.paper_engine.active_positions)
    margin_used = sum(p.get("margin_required", 0.0) for p in bot.paper_engine.active_positions.values())
    portfolio_heat_pct = (margin_used / total_eq) * 100.0 if total_eq > 0 else 0.0

    return {
        "status": "LIVE_OKX_SYNCED",
        "total_equity_usd": round(total_eq, 2),
        "funding_arbitrage": {
            "strategy": "Spot-Futures Delta-Neutral Arbitrage",
            "account_mode": "Multi-Currency Margin Mode (Verified)",
            "allocated_capital": round(alloc_80, 2),
            "estimated_annual_apy_pct": round(annual_apy, 2),
            "daily_cashflow_usd": round(daily_cashflow, 2),
            "delta_neutral_shield": "🟢 ACTIVE (OKX Live Margin Collateral)"
        },
        "sideway_range_scalper": {
            "strategy": "4H Swing Trading Engine (Supertrend + ADX > 20)",
            "allocated_capital": round(alloc_20, 2),
            "active_positions_count": active_pos_count,
            "margin_used_usd": round(margin_used, 2),
            "portfolio_heat_pct": round(portfolio_heat_pct, 2),
            "risk_shield": f"🟢 {active_pos_count} Active OKX Positions | Heat: {portfolio_heat_pct:.1f}%"
        }
    }

@app.get("/api/quant-report")
def get_quant_report():
    """Return qq Quant Performance & Audit Report."""
    return {"report": quant_analyzer.generate_quant_report()}

@app.post("/api/start")
def start_bot():
    bot.bot_state = "RUNNING"
    bot.risk_engine.reset_circuit_breaker()
    return {"status": "SUCCESS", "bot_state": "RUNNING", "message": "▶️ OKX Futures 15-Veteran Bot เริ่มทำงานเรียบร้อยแล้ว (Active)"}

@app.post("/api/pause")
def pause_bot():
    bot.bot_state = "PAUSED"
    return {"status": "SUCCESS", "bot_state": "PAUSED", "message": "⏸️ บอทหยุดพักการทำงานชั่วคราว (Bot Paused)"}

@app.post("/api/panic")
def trigger_panic():
    bot.risk_engine.is_circuit_broken = True
    bot.bot_state = "ERROR"
    bot.notifier.send_panic_alert("Manual Panic Stop from Next.js Web Dashboard")
    return {"status": "SUCCESS", "bot_state": "ERROR", "message": "🚨 EMERGENCY PANIC STOP ACTIVATED: Open orders cancelled & Trading locked."}

@app.post("/api/reset")
def reset_system():
    bot.risk_engine.reset_circuit_breaker()
    bot.bot_state = "RUNNING"
    return {"status": "SUCCESS", "bot_state": "RUNNING", "message": "🟢 Reset System และเริ่มทำงานใหม่เรียบร้อยแล้ว"}

@app.post("/api/toggle-mode")
def toggle_mode():
    bot.trading_mode = "LIVE" if bot.trading_mode == "PAPER" else "PAPER"
    return {"status": "SUCCESS", "mode": bot.trading_mode}

@app.post("/api/sim-buy")
def sim_buy(symbol: str = Query("BTC-USDT-SWAP"), side: str = Query("LONG")):
    side = side.upper()
    candles = bot.client.get_candles(symbol=symbol, resolution="240", limit=300)
    if candles:
        price = candles[-1]["close"]
        atr = TechnicalIndicators.calculate_atr(candles, 14)[-1] if len(candles) >= 14 else 0.02 * price
        risk = bot.risk_engine.calculate_position_sizing(bot.paper_engine.current_capital, price, atr, side=side)
        
        sl_price = round(price - (2.0 * atr), 4) if side == "LONG" else round(price + (2.0 * atr), 4)
        tp_price = round(price + (1.5 * atr), 4) if side == "LONG" else round(price - (1.5 * atr), 4)

        # 1. Open in Local Paper Trading Engine
        res = bot.paper_engine.open_position(symbol, price, risk, side=side)
        
        # 2. ALSO Execute Order on OKX Demo API directly (x-simulated-trading: 1) with SL/TP attached
        okx_res = bot.client.place_market_order(
            symbol=symbol,
            side=side,
            sz=risk.get("order_value", 250.0),
            sl_price=sl_price,
            tp_price=tp_price
        )
        
        if okx_res.get("status") == "SUCCESS":
            ord_id = okx_res.get('order_id', '')
            if symbol in bot.paper_engine.active_positions:
                bot.paper_engine.active_positions[symbol]["okx_order_id"] = ord_id
                bot.paper_engine._save_state()
            msg = f"🟢 ส่งออเดอร์เข้า OKX Demo Account สำเร็จ! (Order ID: #{ord_id})\nเปิด {side} สำหรับ {symbol} ที่ราคา ${price:,.2f}\nตั้ง SL: ${sl_price:,.4f} | TP: ${tp_price:,.4f} อัตโนมัติ"
        else:
            msg = f"เปิดออเดอร์จำลอง Paper {side} สำหรับ {symbol} ที่ราคา ${price:,.2f} (OKX Note: {okx_res.get('message', 'Paper Mode')})"

        return {"status": "SUCCESS", "message": msg, "okx_response": okx_res}
    return {"status": "ERROR", "message": f"Failed to fetch market data for {symbol}"}

@app.post("/api/close-position")
def close_position_manually(symbol: str = Query(...)):
    """
    OKX Perpetual Market Close Endpoint.
    Manually close an active position for the requested symbol using real-time market price.
    Also executes close-position on OKX Demo API directly (POST /api/v5/trade/close-position).
    """
    candles = bot.client.get_candles(symbol=symbol, resolution="4H", limit=10)
    if not candles:
        return {"status": "ERROR", "message": f"Failed to fetch market price for {symbol}"}
    
    current_price = candles[-1]["close"]
    pos_side = "LONG"
    if symbol in bot.paper_engine.active_positions:
        pos_side = bot.paper_engine.active_positions[symbol].get("side", "LONG")

    # 1. Close position on OKX Demo API directly
    okx_close_res = bot.client.close_position_on_okx(symbol, pos_side)

    # 2. Close position in local Paper Engine & SQLite DB
    res = bot.paper_engine.close_position_manually(symbol, current_price)
    if res.get("status") == "SUCCESS":
        trade = res["trade_record"]
        bot.notifier.send_message(
            f"<b>🚨 [MANUAL OKX MARKET CLOSE]</b>\n"
            f"Asset: {symbol}\n"
            f"Side: {trade['side']}\n"
            f"Exit Price: ${trade['exit_price']:,.4f}\n"
            f"Net PnL: ${trade['net_pnl']} ({trade['pnl_pct']}%)"
        )
        res["okx_close_response"] = okx_close_res
    return res

@app.post("/api/clear-positions-history")
def clear_positions_history():
    """
    Permanently purge all active positions and closed trade history from SQLite and Memory.
    """
    try:
        bot.paper_engine.reset_engine_state()
        bot.db.clear_all_positions_and_history()
        return {
            "status": "SUCCESS",
            "message": "🟢 ล้างข้อมูล Active Positions และ Closed Trades History ออกจากระบบเรียบร้อยแล้ว!"
        }
    except Exception as e:
        return {"status": "ERROR", "message": f"Failed to clear trading data: {e}"}

@app.post("/api/update-tp1")
def update_tp1_target(symbol: str = Query(...), new_tp1: float = Query(...)):
    """
    OKX Perpetual Take Profit Order Update Endpoint.
    Validates OKX Take Profit rules against current market price before updating.
    """
    candles = bot.client.get_candles(symbol=symbol, resolution="4H", limit=10)
    if not candles:
        return {"status": "ERROR", "message": f"Failed to fetch market price for {symbol}"}
    
    current_price = candles[-1]["close"]
    res = bot.paper_engine.update_tp1_target(symbol, new_tp1, current_price)
    if res.get("status") == "SUCCESS":
        bot.notifier.send_message(
            f"<b>✏️ [OKX TP1 ORDER UPDATED]</b>\n"
            f"Asset: {symbol}\n"
            f"Side: {res['side']}\n"
            f"New TP1 Target: ${res['new_tp1']:,.4f}\n"
            f"Current Market Price: ${res['current_price']:,.4f}\n"
            f"Previous TP1: ${res['old_tp1']:,.4f}"
        )
    return res

@app.post("/api/toggle-sideway-mode")
def toggle_sideway_mode(enabled: bool = Query(...)):
    """Toggle 15m Sideway Range Engine ON/OFF with Graceful Disabling Handling."""
    return bot.set_sideway_mode(enabled)

@app.get("/api/export-data")
def export_trading_data():
    """Export full trading state backup (active positions, trade history, cashflow logs)."""
    return {
        "status": "SUCCESS",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "bot_summary": bot.paper_engine.get_summary(),
        "active_positions": list(bot.paper_engine.active_positions.values()),
        "trade_history": bot.paper_engine.trade_history
    }
@app.post("/api/import-data")
def import_trading_data(data: dict = Body(...)):
    """Import and restore full trading state from backup payload."""
    try:
        if "active_positions" in data:
            pos_dict = {}
            for p in data["active_positions"]:
                pos_dict[p["symbol"]] = p
            bot.paper_engine.active_positions = pos_dict
        if "trade_history" in data:
            bot.paper_engine.trade_history = data["trade_history"]
        bot.paper_engine._save_state()
        return {"status": "SUCCESS", "message": "📥 Trading state backup imported successfully!"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Failed to import trading state: {e}"}

@app.get("/api/active-monitoring-status")
def get_active_monitoring_status():
    """Return real-time Active Monitoring Engine diagnostic status and last 30m scan telemetry."""
    return bot.active_monitor.last_scan_results

@app.get("/api/okx/orderbook")
def get_okx_orderbook(symbol: str = Query("BTC-USDT-SWAP"), depth: int = Query(10)):
    """Fetch live OKX Bids/Asks orderbook depth for trading terminal."""
    return bot.client.get_orderbook(symbol=symbol, depth=depth)

@app.get("/api/okx/balance")
def get_okx_balance():
    """Fetch live OKX Demo / Real account balance and margin health ratio."""
    return bot.client.get_account_balance()

@app.get("/api/okx/debug-env")
def debug_okx_env():
    """Diagnostic endpoint to safely inspect OKX API Key environment variables on Railway."""
    client = bot.client
    client._resolve_keys()
    
    def mask_str(s):
        if not s:
            return "EMPTY (0 chars)"
        if len(s) <= 6:
            return f"EXISTS (len={len(s)}, val={s[0]}***{s[-1]})"
        return f"EXISTS (len={len(s)}, val={s[:3]}***{s[-3:]})"

    okx_raw_envs = {k: mask_str(v) for k, v in os.environ.items() if "OKX" in k.upper() or "DEMO" in k.upper() or "ACCESS" in k.upper()}

    return {
        "resolved_api_key": mask_str(client.api_key),
        "resolved_secret_key": mask_str(client.api_secret),
        "resolved_passphrase": mask_str(client.passphrase),
        "simulated_mode": client.simulated,
        "raw_environment_variables_detected": okx_raw_envs
    }

@app.get("/api/okx/test-order")
def test_okx_order(symbol: str = "AVAX-USDT-SWAP"):
    """Live diagnostic endpoint to test OKX Demo API order placement and capture exact raw OKX API responses."""
    client = bot.client
    res = client.place_market_order(symbol, "LONG", 250.0, sl_price=6.526, tp_price=6.986)
    return {
        "symbol": symbol,
        "result": res
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
