"""
WebTraderBot FastAPI Backend Server (Railway.app Ready)
Provides REST API services for Next.js Web Dashboard & Telegram Notifier Integration.
Supports OKX Perpetual Swaps & Dual-Direction (LONG/SHORT) Trade Simulations.
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.trader_bot import TraderBot
from src.core.quant_analyzer import QuantAnalyzer

app = FastAPI(
    title="WebTraderBot FastAPI Engine (OKX Futures Edition)",
    description="Multi-Crypto Perpetual Futures Engine for Next.js Dashboard",
    version="3.0.0"
)

# Enable CORS for Next.js frontend (Vercel & Localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bot = TraderBot(
    symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "XRP-USDT-SWAP", "DOGE-USDT-SWAP"],
    resolution="15",
    initial_capital=10000.0
)
quant_analyzer = QuantAnalyzer()

@app.get("/")
def read_root():
    return {"message": "🟢 OKX Futures Trading Engine Backend is Running Live!", "status": bot.bot_state}

@app.get("/api/status")
def get_status():
    """Return real-time bot metrics, prices, indicators, active positions, and trade history."""
    return bot.run_single_iteration()

@app.get("/api/quant-report")
def get_quant_report():
    """Return qq Quant Performance & Audit Report."""
    return {"report": quant_analyzer.generate_quant_report()}

@app.post("/api/start")
def start_bot():
    """Start or Resume the Bot scanning loop."""
    bot.bot_state = "RUNNING"
    bot.risk_engine.reset_circuit_breaker()
    return {"status": "SUCCESS", "bot_state": "RUNNING", "message": "▶️ OKX Futures Bot เริ่มทำงานเรียบร้อยแล้ว (Active)"}

@app.post("/api/pause")
def pause_bot():
    """Pause the Bot scanning loop."""
    bot.bot_state = "PAUSED"
    return {"status": "SUCCESS", "bot_state": "PAUSED", "message": "⏸️ บอทหยุดพักการทำงานชั่วคราว (Bot Paused)"}

@app.post("/api/panic")
def trigger_panic():
    """Trigger Emergency Panic Stop."""
    bot.risk_engine.is_circuit_broken = True
    bot.bot_state = "ERROR"
    bot.notifier.send_panic_alert("Manual Panic Stop from Next.js Web Dashboard")
    return {"status": "SUCCESS", "bot_state": "ERROR", "message": "🚨 EMERGENCY PANIC STOP ACTIVATED: Open orders cancelled & Trading locked."}

@app.post("/api/reset")
def reset_system():
    """Reset Circuit Breaker and resume normal trading."""
    bot.risk_engine.reset_circuit_breaker()
    bot.bot_state = "RUNNING"
    return {"status": "SUCCESS", "bot_state": "RUNNING", "message": "🟢 Reset System และเริ่มทำงานใหม่เรียบร้อยแล้ว"}

@app.post("/api/toggle-mode")
def toggle_mode():
    """Toggle between PAPER and LIVE trading mode."""
    bot.trading_mode = "LIVE" if bot.trading_mode == "PAPER" else "PAPER"
    return {"status": "SUCCESS", "mode": bot.trading_mode}

@app.post("/api/sim-buy")
def sim_buy(symbol: str = Query("BTC-USDT-SWAP"), side: str = Query("LONG")):
    """Simulate a Paper Trading LONG or SHORT Order."""
    side = side.upper()
    candles = bot.client.get_candles(symbol=symbol, resolution="15", limit=300)
    if candles:
        price = candles[-1]["close"]
        atr = 0.02 * price
        risk = bot.risk_engine.calculate_position_sizing(bot.paper_engine.current_capital, price, atr, side=side)
        res = bot.paper_engine.open_position(symbol, price, risk, side=side)
        return {"status": "SUCCESS", "message": f"Simulated Paper {side} Order placed for {symbol} at ${price:,.2f}"}
    return {"status": "ERROR", "message": f"Failed to fetch market data for {symbol}"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
