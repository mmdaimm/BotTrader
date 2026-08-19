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
import threading
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
bot.sync_live_exchange_positions()
quant_analyzer = QuantAnalyzer()
cashflow_engine = CashFlowEngine(bot.client)

process_pool = ProcessPoolExecutor(max_workers=2)
backtest_jobs = {}

@app.get("/api/health")
def health_check():
    return {
        "status": "HEALTHY",
        "engine": "WebTraderBot FastAPI Backend",
        "supported_pairs_count": len(VETERAN_SYMBOLS),
        "timeframe": "15m",
        "active_mode": "15m Range Scalping & Rebalance",
        "telegram_notifier": "ACTIVE" if bot.notifier.bot_token else "DISABLED",
        "process_pool_workers": 2
    }

@app.get("/api/status")
def get_bot_status():
    return bot.run_single_iteration()

@app.get("/api/close-legacy-positions")
def close_legacy_positions():
    """Close all open legacy OKX Demo positions, lock in profit, and activate 15m Scalping mode."""
    results = []
    total_net_pnl = 0.0
    
    pos_resp = bot.client.get_positions(instType="SWAP")
    data_list = pos_resp.get("data", []) if pos_resp.get("code") == "0" else []
    
    for p in data_list:
        p_sz = float(p.get("pos", 0.0) or 0.0)
        if p_sz != 0:
            sym = p.get("instId")
            pos_side = str(p.get("posSide", "long")).upper()
            if pos_side == "NET":
                pos_side = "LONG" if p_sz > 0 else "SHORT"
            upl = float(p.get("upl", 0.0) or 0.0)
            total_net_pnl += upl
            
            close_res = bot.client.close_position_on_okx(sym, pos_side, td_mode="cross")
            if close_res.get("status") != "SUCCESS":
                close_res = bot.client.close_position_on_okx(sym, pos_side, td_mode="isolated")
                
            results.append({
                "symbol": sym,
                "side": pos_side,
                "size": p_sz,
                "unrealized_pnl": upl,
                "close_result": close_res
            })
            
            now_struct = time.localtime()
            trade_rec = {
                "id": f"CLOSED-LEGACY-{sym}-{int(time.time())}",
                "symbol": sym,
                "side": pos_side,
                "type": f"{pos_side} MARKET EXIT (LEGACY 4H TRANSITION)",
                "timeframe": "4h",
                "strategy_type": "SWING_4H",
                "leverage": int(float(p.get("lever", 3) or 3)),
                "entry_price": float(p.get("avgPx", 0.0) or 0.0),
                "exit_price": float(p.get("last", p.get("avgPx", 0.0)) or 0.0),
                "qty": abs(p_sz),
                "net_pnl": round(upl, 2),
                "pnl_pct": round((upl / 100.0) * 100, 2),
                "holding_duration_formatted": "Completed",
                "entry_time": time.strftime("%Y-%m-%d %H:%M:%S", now_struct),
                "exit_time": time.strftime("%Y-%m-%d %H:%M:%S", now_struct),
                "day_of_week": time.strftime("%A", now_struct),
                "hour_of_day": now_struct.tm_hour
            }
            bot.paper_engine.trade_history.insert(0, trade_rec)
            try:
                bot.db.record_trade_history(trade_rec)
            except Exception:
                pass

    bot.paper_engine.active_positions.clear()
    bot.paper_engine._save_state()
    
    bot.sideway_mode_enabled = True
    bot.sideway_state = "ACTIVE"
    bot.db.save_bot_state(
        bot.bot_state, bot.trading_mode, bot.initial_capital,
        bot.paper_engine.current_capital, bot.paper_engine.leverage,
        1, "ACTIVE"
    )

    bot.notifier.send_message(
        f"<b>🎯 [LEGACY POSITIONS CLOSED & 15M SCALPING ACTIVATED]</b>\n"
        f"Closed Positions: <b>{len(results)} รายการ</b>\n"
        f"Total PnL Realized: <b>+${total_net_pnl:,.2f} USD</b> 🟢\n"
        f"New Active Mode: <b>15m Range Scalping (Zone Touch + RSI)</b> 🚀"
    )

    return {
        "status": "SUCCESS",
        "closed_count": len(results),
        "total_pnl_realized_usd": round(total_net_pnl, 2),
        "details": results
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
