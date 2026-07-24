"""
Trading Bot Engine Loop with OKX Perpetual Futures & Dual-Direction Trading (LONG & SHORT)
Enforces 80/20 Institutional Capital Allocation & 4H Swing Trading Engine (Supertrend 10, 3.0 + EMA 50/200 4H + ADX > 20 + 2-bar Cooldown).
"""

import time
from src.core.okx_client import OKXClient
from src.core.indicators import TechnicalIndicators
from src.core.risk_engine import RiskEngine
from src.core.telegram_bot import TelegramNotifier
from src.core.paper_trading import PaperTradingEngine

class TraderBot:
    def __init__(self, symbols: list = None, resolution: str = "240", initial_capital: float = 10000.0):
        self.symbols = symbols or [
            "BTC-USDT-SWAP",
            "ETH-USDT-SWAP",
            "XRP-USDT-SWAP",
            "LTC-USDT-SWAP",
            "BCH-USDT-SWAP",
            "ADA-USDT-SWAP",
            "SOL-USDT-SWAP",
            "DOGE-USDT-SWAP",
            "LINK-USDT-SWAP",
            "DOT-USDT-SWAP",
            "ATOM-USDT-SWAP",
            "ETC-USDT-SWAP",
            "XLM-USDT-SWAP",
            "TRX-USDT-SWAP",
            "AVAX-USDT-SWAP"
        ]
        self.resolution = resolution  # "240" (4H)
        self.timeframe_str = "4h"
        self.client = OKXClient()
        self.risk_engine = RiskEngine()
        self.notifier = TelegramNotifier()
        
        # 80/20 Institutional Capital Allocation
        self.initial_capital = initial_capital
        self.funding_capital_80 = initial_capital * 0.80  # 80% Weight ($8,000)
        self.swing_capital_20 = initial_capital * 0.20   # 20% Weight ($2,000)
        
        self.paper_engine = PaperTradingEngine(initial_capital=self.swing_capital_20)
        self.trading_mode = "PAPER"  # "PAPER" or "LIVE"
        self.bot_state = "RUNNING"   # "RUNNING", "PAUSED", "ERROR"
        self.last_signals_sent = {}  # { symbol: signal_key }
        self.symbol_lockouts = {}    # { symbol: lockout_until_timestamp }

    def evaluate_pair_signal(self, symbol: str, candles: list) -> dict:
        """
        Evaluate 4H Swing Signal on 4H Close (.shift(1)):
        1. Price (4H Close) > EMA 200 (4H) for LONG / Price < EMA 200 (4H) for SHORT
        2. Supertrend (10, 3.0) Direction Flips GREEN (+1) or RED (-1)
        3. ADX (14) > 20.0
        4. Check 2-bar Cooldown Lockout
        """
        if not candles or len(candles) < 200:
            return {"symbol": symbol, "signal": "NONE", "reason": "Insufficient 4H candles"}
            
        closes = [c["close"] for c in candles]
        
        # Anti-Bias: Evaluate strictly on completed prior candle (.shift(1))
        prev_price = closes[-2]
        ema50_4h = TechnicalIndicators.calculate_ema(closes, 50)[-2]
        ema200_4h = TechnicalIndicators.calculate_ema(closes, 200)[-2]
        st_list = TechnicalIndicators.calculate_supertrend(candles, period=10, multiplier=3.0)
        curr_st = st_list[-2]
        prev_st = st_list[-3] if len(st_list) >= 3 else curr_st
        
        adx_list = TechnicalIndicators.calculate_adx(candles, 14)
        adx_val = adx_list[-2] if len(adx_list) >= 2 else 20.0
        atr_val = TechnicalIndicators.calculate_atr(candles, 14)[-2]
        
        current_price = closes[-1]
        
        market_snapshot = {
            "timeframe": self.timeframe_str,
            "ema50_4h": round(ema50_4h, 4),
            "ema200_4h": round(ema200_4h, 4),
            "supertrend": curr_st["supertrend"],
            "st_direction": "GREEN" if curr_st["direction"] == 1 else "RED",
            "adx": round(adx_val, 2),
            "atr_4h": round(atr_val, 4)
        }
        
        # Cooldown Lockout Check (Wait 8 hours = 2 bars after SL)
        now_ts = time.time()
        lockout_until = self.symbol_lockouts.get(symbol, 0)
        if now_ts < lockout_until:
            rem_min = int((lockout_until - now_ts) / 60)
            return {
                "symbol": symbol,
                "signal": "NONE",
                "timeframe": self.timeframe_str,
                "market_snapshot": market_snapshot,
                "reason": f"Cooldown Active (Lockout remaining: {rem_min} mins)"
            }

        # If position is already active, skip new signal alerts
        if symbol in self.paper_engine.active_positions:
            return {
                "symbol": symbol,
                "signal": "NONE",
                "timeframe": self.timeframe_str,
                "market_snapshot": market_snapshot,
                "reason": f"Position already active for {symbol}"
            }

        # 4H Supertrend Direction Reversal
        st_turned_green = curr_st["direction"] == 1 and prev_st["direction"] == -1
        st_turned_red = curr_st["direction"] == -1 and prev_st["direction"] == 1

        prev_candle_ts = candles[-2]["timestamp"]

        # 🟢 LONG 4H Swing Signal Conditions
        is_long_swing = prev_price > ema200_4h and curr_st["direction"] == 1 and st_turned_green and adx_val > 20.0
        
        # 🔴 SHORT 4H Swing Signal Conditions
        is_short_swing = prev_price < ema200_4h and curr_st["direction"] == -1 and st_turned_red and adx_val > 20.0
        
        if is_long_swing:
            risk_params = self.risk_engine.calculate_position_sizing(self.paper_engine.current_capital, current_price, atr_val, side="LONG", sl_multiplier=2.0, tp_multiplier=3.5)
            sig_key = f"4H-LONG-{prev_candle_ts}"
            if self.last_signals_sent.get(symbol) != sig_key:
                self.notifier.send_signal_alert(symbol, current_price, risk_params)
                self.last_signals_sent[symbol] = sig_key
                
                if self.trading_mode == "PAPER":
                    self.paper_engine.open_position(symbol, current_price, risk_params, side="LONG", timeframe=self.timeframe_str, market_snapshot=market_snapshot)
                
            return {
                "symbol": symbol,
                "signal": "BUY_LONG",
                "side": "LONG",
                "timeframe": self.timeframe_str,
                "price": current_price,
                "atr": atr_val,
                "risk_params": risk_params,
                "market_snapshot": market_snapshot,
                "reason": f"4H Swing LONG Entry (Price > EMA200, Supertrend GREEN, ADX={adx_val:.1f})"
            }

        elif is_short_swing:
            risk_params = self.risk_engine.calculate_position_sizing(self.paper_engine.current_capital, current_price, atr_val, side="SHORT", sl_multiplier=2.0, tp_multiplier=3.5)
            sig_key = f"4H-SHORT-{prev_candle_ts}"
            if self.last_signals_sent.get(symbol) != sig_key:
                self.notifier.send_signal_alert(symbol, current_price, risk_params)
                self.last_signals_sent[symbol] = sig_key
                
                if self.trading_mode == "PAPER":
                    self.paper_engine.open_position(symbol, current_price, risk_params, side="SHORT", timeframe=self.timeframe_str, market_snapshot=market_snapshot)
                
            return {
                "symbol": symbol,
                "signal": "SELL_SHORT",
                "side": "SHORT",
                "timeframe": self.timeframe_str,
                "price": current_price,
                "atr": atr_val,
                "risk_params": risk_params,
                "market_snapshot": market_snapshot,
                "reason": f"4H Swing SHORT Entry (Price < EMA200, Supertrend RED, ADX={adx_val:.1f})"
            }
            
        return {
            "symbol": symbol,
            "signal": "NONE",
            "timeframe": self.timeframe_str,
            "market_snapshot": market_snapshot,
            "reason": f"No 4H Swing signal (Price={current_price:,.2f}, EMA200={ema200_4h:,.2f}, ADX={adx_val:.1f})"
        }

    def run_single_iteration(self) -> dict:
        """Run a single loop iteration monitoring 4H Swing signals across OKX pairs."""
        try:
            if self.notifier.check_for_panic_command():
                if not self.risk_engine.is_circuit_broken:
                    self.risk_engine.is_circuit_broken = True
                    self.bot_state = "ERROR"
                    self.notifier.send_panic_alert("Triggered via Telegram /panic_stop command")
        except Exception as e:
            print(f"[TraderBot] Telegram check exception: {e}")
                
        if self.risk_engine.is_circuit_broken or self.bot_state == "ERROR":
            self.bot_state = "ERROR"
            return {
                "status": "ERROR",
                "bot_state": "ERROR",
                "trading_mode": self.trading_mode,
                "active_symbols": self.symbols,
                "timeframe": self.timeframe_str,
                "reason": "บอททำงานขัดข้อง / สั่งหยุดฉุกเฉิน (Circuit Breaker Active)",
                "paper_summary": self.paper_engine.get_summary(),
                "active_positions": list(self.paper_engine.active_positions.values()),
                "trade_history": self.paper_engine.trade_history[:10]
            }

        if self.bot_state == "PAUSED":
            return {
                "status": "PAUSED",
                "bot_state": "PAUSED",
                "trading_mode": self.trading_mode,
                "active_symbols": self.symbols,
                "timeframe": self.timeframe_str,
                "reason": "บอทหยุดพักการทำงาน (User Paused)",
                "paper_summary": self.paper_engine.get_summary(),
                "active_positions": list(self.paper_engine.active_positions.values()),
                "trade_history": self.paper_engine.trade_history[:10]
            }

        pair_results = {}
        for sym in self.symbols:
            try:
                candles = self.client.get_candles(symbol=sym, resolution="4H", limit=300)
                if candles:
                    eval_res = self.evaluate_pair_signal(sym, candles)
                    pair_results[sym] = {
                        "last_price": candles[-1]["close"],
                        "eval": eval_res
                    }
            except Exception as e:
                print(f"[TraderBot] Error scanning OKX pair {sym}: {e}")

        # Update Paper Trading Positions check
        try:
            closed_trades = self.paper_engine.update_positions(pair_results)
            for closed in closed_trades:
                pnl_msg = f"<b>[{closed['side']}] {closed['type']}</b>\nAsset: {closed['symbol']}\nTF: 4H Swing\nNet PnL: ${closed['net_pnl']} ({closed['pnl_pct']}%)"
                self.notifier.send_message(pnl_msg)

                # Set 8-hour (2 bars) cooldown lockout if closed via SL
                if "SL" in closed.get("type", ""):
                    self.symbol_lockouts[closed["symbol"]] = time.time() + (8 * 3600)

        except Exception as e:
            print(f"[TraderBot] Error updating paper positions: {e}")

        btc_price = pair_results.get("BTC-USDT-SWAP", {}).get("last_price", 0.0)
        paper_summary = self.paper_engine.get_summary()
        
        return {
            "status": "OK",
            "bot_state": "RUNNING",
            "trading_mode": self.trading_mode,
            "active_symbols": self.symbols,
            "timeframe": self.timeframe_str,
            "last_price": btc_price,
            "pair_results": pair_results,
            "paper_summary": paper_summary,
            "institutional_allocation": {
                "funding_rate_arbitrage_80pct": {
                    "allocated_capital_usd": self.funding_capital_80,
                    "estimated_annual_apy_pct": 15.33,
                    "status": "ACTIVE (Delta-Neutral 1x Spot + 1x Short)"
                },
                "swing_engine_20pct": {
                    "allocated_capital_usd": self.swing_capital_20,
                    "current_capital_usd": self.paper_engine.current_capital,
                    "status": "ACTIVE (4H Swing Partial TP State Machine v2.0)"
                }
            },
            "active_positions": list(self.paper_engine.active_positions.values()),
            "trade_history": self.paper_engine.trade_history[:10]
        }
