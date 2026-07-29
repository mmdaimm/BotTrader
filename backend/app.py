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
    return {
        "status": "ONLINE",
        "service": "WebTraderBot FastAPI Engine (OKX 15-Veteran Futures Portfolio)",
        "version": "5.1.0-OKX-DEMO",
        "trading_mode": bot.trading_mode,
        "bot_state": bot.bot_state,
        "sideway_mode_enabled": bot.sideway_mode_enabled,
        "sideway_state": bot.sideway_state,
        "symbols_count": len(bot.symbols)
    }

@app.get("/api/status")
def get_bot_status():
    """Return real-time bot state, active positions, indicators, and paper trading statistics."""
    try:
        return bot.run_single_iteration()
    except Exception as e:
        return {
            "status": "ERROR",
            "message": str(e),
            "bot_state": bot.bot_state
        }

@app.get("/api/cashflow-summary")
def get_cashflow_summary():
    """Return Daily Cash Flow Dashboard Engine metrics, yield analytics, and profit pool breakdown."""
    try:
        current_status = bot.run_single_iteration()
        summary = cashflow_engine.calculate_cashflow_summary(
            paper_engine=bot.paper_engine,
            current_status=current_status
        )
        return summary
    except Exception as e:
        return {
            "status": "ERROR",
            "message": str(e)
        }

@app.post("/api/backtest/start")
def start_backtest_job(
    background_tasks: BackgroundTasks,
    symbol: str = Query("BTC-USDT-SWAP"),
    timeframe: str = Query("4h"),
    period_days: int = Query(30)
):
    """Trigger an asynchronous, non-blocking quantitative backtest job."""
    job_id = str(uuid.uuid4())
    backtest_jobs[job_id] = {
        "job_id": job_id,
        "status": "RUNNING",
        "symbol": symbol,
        "timeframe": timeframe,
        "period_days": period_days,
        "progress_pct": 10,
        "result": None
    }
    
    future = process_pool.submit(run_backtest_process, symbol, timeframe, period_days)
    
    def on_complete(fut):
        try:
            res = fut.result()
            backtest_jobs[job_id]["status"] = "COMPLETED"
            backtest_jobs[job_id]["progress_pct"] = 100
            backtest_jobs[job_id]["result"] = res
        except Exception as ex:
            backtest_jobs[job_id]["status"] = "FAILED"
            backtest_jobs[job_id]["error"] = str(ex)

    future.add_done_callback(on_complete)

    return {
        "status": "ACCEPTED",
        "job_id": job_id,
        "message": f"Backtest job for {symbol} ({period_days} days) started in background."
    }

@app.get("/api/backtest/status")
def get_backtest_job_status(job_id: str = Query(...)):
    """Check status and retrieve results for a background backtest job."""
    if job_id not in backtest_jobs:
        return {"status": "NOT_FOUND", "message": "Invalid job_id"}
    return backtest_jobs[job_id]

@app.post("/api/close-position")
def close_position_endpoint(symbol: str = Query(...)):
    """Manual emergency close endpoint for active position."""
    if symbol in bot.paper_engine.active_positions:
        pos = bot.paper_engine.active_positions[symbol]
        curr_price = pos.get("entry_price", 0.0)
        candles = bot.client.get_candles(symbol, resolution="15", limit=5)
        if candles:
            curr_price = candles[-1]["close"]
        res = bot.paper_engine.close_position_manually(symbol, curr_price)
        bot.notifier.send_message(
            f"<b>🛑 [MANUAL EMERGENCY CLOSE]</b>\n"
            f"Asset: {symbol}\n"
            f"Exit Price: ${curr_price:,.4f}\n"
            f"Net PnL: ${res.get('trade_record', {}).get('net_pnl', 0.0):,.2f}"
        )
        return res
    return {"status": "ERROR", "message": f"No active position found for {symbol}"}

@app.post("/api/update-tp1")
def update_tp1_endpoint(symbol: str = Query(...), new_tp1: float = Query(...)):
    """Update Take Profit 1 (TP1) target price for an open position."""
    res = bot.paper_engine.update_tp1_price(symbol, new_tp1)
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
        "status": "SUCCESS",
        "api_key": mask_str(client.api_key),
        "api_secret": mask_str(client.api_secret),
        "passphrase": mask_str(client.passphrase),
        "simulated_mode": client.simulated,
        "raw_environment_variables_detected": okx_raw_envs
    }

@app.get("/api/okx/test-order")
def test_okx_order(symbol: str = "UNI-USDT-SWAP"):
    """Live diagnostic endpoint to test OKX Demo API order placement and capture exact raw OKX API responses."""
    client = bot.client
    res = client.place_market_order(symbol, "LONG", 1.0, sl_price=3.78, tp_price=4.18)
    return {
        "symbol": symbol,
        "result": res
    }

@app.get("/api/trigger-test-order")
def trigger_test_order(symbol: str = Query("UNI-USDT-SWAP"), side: str = Query("LONG"), sz: float = Query(1.0)):
    """
    Trigger a REAL order execution test on OKX Demo Account (x-simulated-trading: 1).
    Places order directly via OKX API v5 and records position on PaperTradingEngine.
    """
    try:
        # 1. Fetch current market price
        candles = bot.client.get_candles(symbol=symbol, resolution="240", limit=10)
        current_price = candles[-1]["close"] if candles else 3.984
        
        p_lower = round(current_price * 0.95, 4)
        p_upper = round(current_price * 1.05, 4)

        # 2. Execute order on OKX Demo API
        okx_res = bot.client.place_market_order(
            symbol=symbol,
            side=side,
            sz=sz,
            sl_price=p_lower,
            tp_price=p_upper
        )
        
        # 3. Record position on Paper Trading Engine
        risk_params = {
            "position_qty": sz,
            "sl_price": p_lower,
            "tp_price": p_upper
        }
        paper_res = bot.paper_engine.open_position(
            symbol=symbol,
            entry_price=current_price,
            risk_params=risk_params,
            side=side,
            market_snapshot={"strategy_type": "GEOMETRIC_GRID_FUTURES", "p_lower": p_lower, "p_upper": p_upper}
        )

        # 4. Telegram Notification
        bot.notifier.send_message(
            f"<b>🚀 [OKX DEMO GRID ORDER EXECUTED]</b>\n"
            f"Asset: <b>{symbol}</b> ({side})\n"
            f"Entry Price: ${current_price:,.4f}\n"
            f"SL: ${p_lower:,.4f} | TP: ${p_upper:,.4f}\n"
            f"OKX Status: {okx_res.get('status')}"
        )

        return {
            "status": "SUCCESS",
            "symbol": symbol,
            "side": side,
            "current_price": current_price,
            "okx_demo_response": okx_res,
            "paper_engine_response": paper_res
        }
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
