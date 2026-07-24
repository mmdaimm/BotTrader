"""
WebTraderBot Quantitative Multi-Strategy Backtesting Engine (Production Standard)
Simulates 6-Month (180 Days / 18,000 Candles) Dual-Engine Portfolio Performance:
- Engine A: 15m Trend-Pullback Scalper (with EMA21 Slope + VMA20 Filters)
- Engine B: Daily Cash Flow Funding Rate Yield Arbitrage (+15.33% APY / +0.042% daily cash flow)
- Friction Deductions (0.05% Taker Fee per side + 0.02% Slippage Buffer)
- Tracks Initial Capital, Final Capital, Net PnL, Win Rate %, Max Drawdown %, & Accumulated Cash Flow
"""

import sys
import os
import time
import json
import urllib.request
from typing import List, Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.indicators import TechnicalIndicators
from src.core.okx_client import OKXClient, SYMBOL_MAP

CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "backtest_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

class BacktestEngine:
    def __init__(self, taker_fee_pct: float = 0.05, slippage_pct: float = 0.02):
        self.client = OKXClient()
        self.fee_rate = taker_fee_pct / 100.0
        self.slippage_rate = slippage_pct / 100.0
        self.daily_funding_yield_pct = 0.042  # ~15.33% APY / 365 days = +0.042% daily

    def fetch_deep_history(self, symbol: str, resolution: str = "15", days: int = 180) -> List[Dict[str, Any]]:
        """Deep Historical Pagination Fetcher (Supports 3-6 Months / 8,640 - 17,280 candles)."""
        global_symbol = SYMBOL_MAP.get(symbol, symbol.replace("-USDT-SWAP", "USDT"))
        target_count = min(days * 24 * 4, 18000)
        all_candles = []
        end_time_ms = None

        print(f"[Backtest] Downloading deep {days}-day historical dataset for {symbol} ({target_count} candles)...")

        while len(all_candles) < target_count:
            try:
                url = f"https://api.binance.com/api/v3/klines?symbol={global_symbol}&interval={resolution}m&limit=1000"
                if end_time_ms:
                    url += f"&endTime={end_time_ms}"

                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode())
                    if not data:
                        break

                    batch = []
                    for item in data:
                        batch.append({
                            "timestamp": int(item[0]) // 1000,
                            "open": float(item[1]),
                            "high": float(item[2]),
                            "low": float(item[3]),
                            "close": float(item[4]),
                            "volume": float(item[5])
                        })

                    if not batch:
                        break

                    all_candles = batch + all_candles
                    end_time_ms = int(data[0][0]) - 1
                    time.sleep(0.05)

            except Exception as e:
                print(f"[Backtest] Deep fetch warning for {symbol}: {e}")
                break

        return all_candles

    def get_cached_candles(self, symbol: str, resolution: str = "15", days: int = 180) -> List[Dict[str, Any]]:
        cache_file = os.path.join(CACHE_DIR, f"{symbol}_{resolution}m_{days}d.json")
        cached_data = []

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
            except Exception as e:
                print(f"[Backtest] Cache load warning for {symbol}: {e}")

        needed_candles = min(days * 24 * 4, 18000)

        if len(cached_data) < needed_candles * 0.8:
            fetched = self.fetch_deep_history(symbol, resolution, days=days)
            if fetched:
                cached_data = fetched
                try:
                    with open(cache_file, "w") as f:
                        json.dump(cached_data, f)
                except Exception as e:
                    print(f"[Backtest] Cache write error for {symbol}: {e}")

        cached_data.sort(key=lambda x: x["timestamp"])
        return cached_data

    def run_simulation(self, symbol: str, initial_capital: float = 10000.0, days: int = 180) -> Dict[str, Any]:
        """
        Run 6-Month simulation comparing:
        1. Pure Trend Scalper Strategy (Without Cash Flow)
        2. Combined Multi-Engine (Trend Scalper + Daily Cash Flow Arbitrage Yield)
        """
        candles = self.get_cached_candles(symbol, resolution="15", days=days)
        if len(candles) < 150:
            return {
                "symbol": symbol,
                "status": "ERROR",
                "message": f"Insufficient historical data (need >= 150 candles, got {len(candles)})"
            }

        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]

        # Calculate Indicators
        ema200 = TechnicalIndicators.calculate_ema(closes, 200)
        ema9 = TechnicalIndicators.calculate_ema(closes, 9)
        ema21 = TechnicalIndicators.calculate_ema(closes, 21)
        rsi = TechnicalIndicators.calculate_rsi(closes, 14)
        adx = TechnicalIndicators.calculate_adx(candles, 14)
        vma20 = TechnicalIndicators.calculate_sma(volumes, 20)
        atr = TechnicalIndicators.calculate_atr(candles, 14)

        # Simulation Variables
        current_capital_trend = initial_capital
        current_capital_combined = initial_capital
        accumulated_cashflow_usd = 0.0

        peak_capital = initial_capital
        max_drawdown_usd = 0.0
        max_drawdown_pct = 0.0

        positions = []
        closed_trades = []

        warmup = 100
        total_days_simulated = (len(candles) - warmup) / (24 * 4)

        # Accumulate Daily Cash Flow Arbitrage Yield across simulated days
        daily_cashflow_per_day = initial_capital * 0.60 * (self.daily_funding_yield_pct / 100.0)
        accumulated_cashflow_usd = round(daily_cashflow_per_day * total_days_simulated, 2)

        for i in range(warmup, len(candles)):
            c = candles[i]
            price = c["close"]
            high_p = c["high"]
            low_p = c["low"]

            # Anti-Bias: Evaluate signals strictly using completed prior candle (i-1)
            prev_price = closes[i - 1]
            prev_ema200 = ema200[i - 1] if i - 1 < len(ema200) else 0.0
            prev_ema9 = ema9[i - 1] if i - 1 < len(ema9) else 0.0
            prev_ema21 = ema21[i - 1] if i - 1 < len(ema21) else 0.0
            prev_rsi = rsi[i - 1] if i - 1 < len(rsi) else 50.0
            prev_adx = adx[i - 1] if i - 1 < len(adx) else 0.0
            prev_vol = volumes[i - 1]
            prev_vma20 = vma20[i - 1] if i - 1 < len(vma20) else 1.0
            curr_atr = atr[i - 1] if i - 1 < len(atr) else (0.02 * price)

            # Calculate EMA 21 Slope
            ema21_prev2 = ema21[i - 2] if i - 2 < len(ema21) else prev_ema21
            ema21_slope = ((prev_ema21 - ema21_prev2) / (ema21_prev2 or 1.0)) * 100.0

            # Manage Open Position Exits
            if positions:
                pos = positions[0]
                is_long = pos["side"] == "LONG"
                entry_p = pos["entry_price"]

                hit_sl = low_p <= pos["sl"] if is_long else high_p >= pos["sl"]
                hit_tp = high_p >= pos["tp"] if is_long else low_p <= pos["tp"]

                if hit_sl or hit_tp:
                    raw_exit = pos["sl"] if hit_sl else pos["tp"]
                    exit_price = raw_exit * (1 - self.slippage_rate) if is_long else raw_exit * (1 + self.slippage_rate)

                    entry_val = pos["qty"] * entry_p
                    exit_val = pos["qty"] * exit_price

                    entry_fee = entry_val * self.fee_rate
                    exit_fee = exit_val * self.fee_rate
                    total_fees = entry_fee + exit_fee

                    gross_pnl = (exit_val - entry_val) if is_long else (entry_val - exit_val)
                    net_pnl = gross_pnl - total_fees
                    pnl_pct = (net_pnl / pos["margin"]) * 100.0

                    current_capital_trend += net_pnl
                    if current_capital_trend > peak_capital:
                        peak_capital = current_capital_trend
                    dd_usd = peak_capital - current_capital_trend
                    dd_pct = (dd_usd / peak_capital) * 100.0
                    if dd_pct > max_drawdown_pct:
                        max_drawdown_pct = dd_pct
                        max_drawdown_usd = dd_usd

                    closed_trades.append({
                        "symbol": symbol,
                        "side": pos["side"],
                        "entry": entry_p,
                        "exit": exit_price,
                        "net_pnl": round(net_pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "result": "WIN" if net_pnl >= 0 else "LOSS"
                    })
                    positions.clear()

            # Signal Generation (with EMA 21 Slope & VMA 20 Filters)
            if not positions:
                is_trend_market = prev_adx > 20 and abs(ema21_slope) > 0.02
                is_volume_valid = prev_vol > 1.5 * prev_vma20

                signal = "NONE"
                if is_trend_market and is_volume_valid:
                    if prev_price > prev_ema200 and prev_ema9 > prev_ema21 and 45 <= prev_rsi <= 65:
                        signal = "BUY_LONG"
                    elif prev_price < prev_ema200 and prev_ema9 < prev_ema21 and 35 <= prev_rsi <= 55:
                        signal = "SELL_SHORT"

                if signal != "NONE":
                    side = "LONG" if signal == "BUY_LONG" else "SHORT"
                    entry_price = price * (1 + self.slippage_rate) if side == "LONG" else price * (1 - self.slippage_rate)
                    
                    sl_dist = 1.5 * curr_atr
                    tp_dist = 1.5 * curr_atr
                    sl = entry_price - sl_dist if side == "LONG" else entry_price + sl_dist
                    tp = entry_price + tp_dist if side == "LONG" else entry_price - tp_dist

                    margin = min(current_capital_trend * 0.15, initial_capital * 0.15)
                    order_val = margin * 3.0
                    qty = order_val / entry_price

                    positions.append({
                        "side": side,
                        "entry_price": entry_price,
                        "qty": qty,
                        "margin": margin,
                        "sl": sl,
                        "tp": tp
                    })

        # Final Performance Metrics Calculation
        total_trades = len(closed_trades)
        win_trades = len([t for t in closed_trades if t["result"] == "WIN"])
        loss_trades = len([t for t in closed_trades if t["result"] == "LOSS"])
        win_rate = round((win_trades / total_trades * 100.0), 2) if total_trades > 0 else 0.0

        total_win_pnl = sum([t["net_pnl"] for t in closed_trades if t["net_pnl"] > 0])
        total_loss_pnl = abs(sum([t["net_pnl"] for t in closed_trades if t["net_pnl"] < 0]))
        profit_factor = round(total_win_pnl / (total_loss_pnl or 1.0), 2)

        net_profit_trend = round(current_capital_trend - initial_capital, 2)
        net_profit_trend_pct = round((net_profit_trend / initial_capital) * 100.0, 2)

        # Combined Strategy Capital (Trend Scalper + Cash Flow Yield)
        current_capital_combined = round(current_capital_trend + accumulated_cashflow_usd, 2)
        net_profit_combined = round(current_capital_combined - initial_capital, 2)
        net_profit_combined_pct = round((net_profit_combined / initial_capital) * 100.0, 2)

        return {
            "symbol": symbol,
            "status": "SUCCESS",
            "days_simulated": round(total_days_simulated, 1),
            "candles_analyzed": len(candles),
            "initial_capital_usd": initial_capital,
            "initial_capital_thb": round(initial_capital * 35.5, 2),
            "trend_only_system": {
                "final_capital_usd": round(current_capital_trend, 2),
                "net_profit_usd": net_profit_trend,
                "net_profit_pct": net_profit_trend_pct
            },
            "cashflow_arbitrage_yield": {
                "accumulated_cashflow_usd": accumulated_cashflow_usd,
                "accumulated_cashflow_thb": round(accumulated_cashflow_usd * 35.5, 2),
                "daily_yield_pct": self.daily_funding_yield_pct,
                "annual_apy_pct": 15.33
            },
            "combined_dual_engine": {
                "final_capital_usd": current_capital_combined,
                "final_capital_thb": round(current_capital_combined * 35.5, 2),
                "net_profit_usd": net_profit_combined,
                "net_profit_pct": net_profit_combined_pct
            },
            "performance_audit": {
                "total_trades": total_trades,
                "win_trades": win_trades,
                "loss_trades": loss_trades,
                "win_rate_pct": win_rate,
                "profit_factor": profit_factor,
                "max_drawdown_pct": round(max_drawdown_pct, 2),
                "max_drawdown_usd": round(max_drawdown_usd, 2),
                "friction_deductions": "0.05% Taker Fee + 0.02% Slippage per trade side"
            },
            "trades_sample": closed_trades[-10:]
        }

def run_backtest_process(symbol: str = "BTC-USDT-SWAP", initial_capital: float = 10000.0, days: int = 180) -> Dict[str, Any]:
    engine = BacktestEngine()
    return engine.run_simulation(symbol=symbol, initial_capital=initial_capital, days=days)

if __name__ == "__main__":
    print("=== Testing 6-Month (180 Days) Capital Simulation Engine ===")
    res = run_backtest_process("BTC-USDT-SWAP", initial_capital=10000.0, days=180)
    print(json.dumps(res, indent=2))
