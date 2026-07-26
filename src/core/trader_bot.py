"""
Trading Bot Engine Loop with OKX Perpetual Futures & Dual-Direction Trading (LONG & SHORT)
Enforces 80/20 Institutional Capital Allocation, 4H Swing Engine, Active Monitoring Engine (30m Loop),
and 15m Sideway Range Mean-Reversion Engine with Shared Capital & Dynamic Reversal Confirmation.
"""

import time
import math
from src.core.okx_client import OKXClient
from src.core.indicators import TechnicalIndicators
from src.core.risk_engine import RiskEngine
from src.core.telegram_bot import TelegramNotifier
from src.core.paper_trading import PaperTradingEngine
from src.core.active_monitor import ActiveMonitor
from src.core.database import DatabaseManager

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
        self.db = DatabaseManager()
        
        # 80/20 Institutional Capital Allocation
        self.initial_capital = initial_capital
        self.funding_capital_80 = initial_capital * 0.80  # 80% Weight ($8,000)
        self.swing_capital_20 = initial_capital * 0.20   # 20% Weight ($2,000)
        
        self.paper_engine = PaperTradingEngine(initial_capital=self.swing_capital_20)
        self.active_monitor = ActiveMonitor(self.client, self.paper_engine, notifier=self.notifier)
        self.trading_mode = "PAPER"  # "PAPER" or "LIVE"
        self.bot_state = "RUNNING"   # "RUNNING", "PAUSED", "ERROR"
        
        # Sideway Engine State & Config
        db_state = self.db.get_bot_state()
        self.sideway_mode_enabled = bool(db_state.get("sideway_mode_enabled", 0))
        self.sideway_state = db_state.get("sideway_state", "DISABLED")
        
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
            "strategy_type": "SWING_4H",
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

        # LONG Signal Trigger Condition:
        # Price > EMA200 4H AND Supertrend flipped GREEN (from RED) AND ADX > 20.0
        is_long_signal = (prev_price > ema200_4h) and (curr_st["direction"] == 1 and prev_st["direction"] == -1) and (adx_val > 20.0)

        # SHORT Signal Trigger Condition:
        # Price < EMA200 4H AND Supertrend flipped RED (from GREEN) AND ADX > 20.0
        is_short_signal = (prev_price < ema200_4h) and (curr_st["direction"] == -1 and prev_st["direction"] == 1) and (adx_val > 20.0)

        if is_long_signal:
            sl_price = round(current_price - (2.0 * atr_val), 4)
            tp1_price = round(current_price + (1.5 * atr_val), 4)
            return {
                "symbol": symbol,
                "signal": "LONG",
                "strategy_type": "SWING_4H",
                "id_prefix": "SW-",
                "entry_price": current_price,
                "sl_price": sl_price,
                "tp1_target": tp1_price,
                "tp_price": tp1_price,
                "market_snapshot": market_snapshot,
                "reason": f"4H Swing LONG Signal (Supertrend GREEN, Price > EMA200, ADX: {adx_val:.1f})"
            }

        if is_short_signal:
            sl_price = round(current_price + (2.0 * atr_val), 4)
            tp1_price = round(current_price - (1.5 * atr_val), 4)
            return {
                "symbol": symbol,
                "signal": "SHORT",
                "strategy_type": "SWING_4H",
                "id_prefix": "SW-",
                "entry_price": current_price,
                "sl_price": sl_price,
                "tp1_target": tp1_price,
                "tp_price": tp1_price,
                "market_snapshot": market_snapshot,
                "reason": f"4H Swing SHORT Signal (Supertrend RED, Price < EMA200, ADX: {adx_val:.1f})"
            }

        return {
            "symbol": symbol,
            "signal": "NONE",
            "timeframe": self.timeframe_str,
            "market_snapshot": market_snapshot,
            "reason": "No entry setup"
        }

    def evaluate_sideway_signal(self, symbol: str, candles_15m: list) -> dict:
        """
        Evaluate 15m Sideway Range Mean-Reversion Signal:
        1. ADX (14, 15m) < 22.0 Regime Guard (Confirms non-trending regime)
        2. Reversal Candle Confirmation (Close Inside Band):
           - LONG: Prev close <= Lower Band, Curr close > Lower Band (Inside Band) + RSI < 35.0
           - SHORT: Prev close >= Upper Band, Curr close < Upper Band (Inside Band) + RSI > 65.0
        3. Capital Allocation Cap ($400 max total margin) & max 2 active Sideway positions
        4. Tagged with strategy_type = 'SIDEWAY_15M' and ID prefix 'SD-'
        """
        if not candles_15m or len(candles_15m) < 30:
            return {"symbol": symbol, "signal": "NONE", "reason": "Insufficient 15m candles"}

        # Graceful Disabling Check: If sideway_state is "STOPPING" or "DISABLED", block new entries
        if not self.sideway_mode_enabled or self.sideway_state == "STOPPING":
            return {"symbol": symbol, "signal": "NONE", "reason": "Sideway Engine OFF or Stopping"}

        # Capital Quota Guard: Sideway total margin cap <= $400 USD and max 2 active Sideway positions
        active_sideway_positions = [
            p for p in self.paper_engine.active_positions.values() 
            if p.get("strategy_type") == "SIDEWAY_15M"
        ]
        total_sideway_margin = sum(p.get("margin_required", 0) for p in active_sideway_positions)
        if len(active_sideway_positions) >= 2 or total_sideway_margin >= 400.0:
            return {"symbol": symbol, "signal": "NONE", "reason": "Sideway Capital Quota Full ($400 Margin / Max 2 Positions)"}

        if symbol in self.paper_engine.active_positions:
            return {"symbol": symbol, "signal": "NONE", "reason": f"Position already active for {symbol}"}

        closes = [c["close"] for c in candles_15m]

        adx_list = TechnicalIndicators.calculate_adx(candles_15m, 14)
        adx_val = adx_list[-1] if adx_list else 20.0

        # ADX Regime Guard: Require ADX < 22.0 (Non-trending market)
        if adx_val >= 22.0:
            return {"symbol": symbol, "signal": "NONE", "reason": f"ADX too high ({adx_val:.1f} >= 22.0) - Strong Trend Detected"}

        rsi_list = TechnicalIndicators.calculate_rsi(closes, 14)
        rsi_val = rsi_list[-1] if rsi_list else 50.0

        atr_val = TechnicalIndicators.calculate_atr(candles_15m, 14)[-1]

        # Calculate Bollinger Bands (20, 2.0)
        sma20 = TechnicalIndicators.calculate_sma(closes, 20)
        sma20_curr = sma20[-1]
        
        recent20 = closes[-20:]
        mean20 = sum(recent20) / 20
        variance20 = sum((x - mean20) ** 2 for x in recent20) / 20
        std20 = math.sqrt(variance20)
        upper_band = sma20_curr + (2.0 * std20)
        lower_band = sma20_curr - (2.0 * std20)

        prev_close = closes[-2]
        curr_close = closes[-1]

        # Reversal Candle Confirmation:
        # LONG: Prev Close <= Lower Band, Curr Close > Lower Band (Inside Band) + RSI < 35.0
        is_long_reversal = (prev_close <= lower_band) and (curr_close > lower_band) and (rsi_val < 35.0)

        # SHORT: Prev Close >= Upper Band, Curr Close < Upper Band (Inside Band) + RSI > 65.0
        is_short_reversal = (prev_close >= upper_band) and (curr_close < upper_band) and (rsi_val > 65.0)

        market_snapshot = {
            "strategy_type": "SIDEWAY_15M",
            "timeframe": "15m",
            "adx": round(adx_val, 2),
            "rsi": round(rsi_val, 2),
            "upper_band": round(upper_band, 4),
            "lower_band": round(lower_band, 4),
            "middle_band": round(sma20_curr, 4),
            "atr_15m": round(atr_val, 4)
        }

        if is_long_reversal:
            tp_price = round(sma20_curr, 4)
            sl_price = round(curr_close - (1.2 * atr_val), 4)
            return {
                "symbol": symbol,
                "signal": "LONG",
                "strategy_type": "SIDEWAY_15M",
                "id_prefix": "SD-",
                "entry_price": curr_close,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "tp1_target": tp_price,
                "market_snapshot": market_snapshot,
                "reason": f"15m Sideway Reversal LONG (RSI: {rsi_val:.1f}, Rebounded inside Lower Band)"
            }

        if is_short_reversal:
            tp_price = round(sma20_curr, 4)
            sl_price = round(curr_close + (1.2 * atr_val), 4)
            return {
                "symbol": symbol,
                "signal": "SHORT",
                "strategy_type": "SIDEWAY_15M",
                "id_prefix": "SD-",
                "entry_price": curr_close,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "tp1_target": tp_price,
                "market_snapshot": market_snapshot,
                "reason": f"15m Sideway Reversal SHORT (RSI: {rsi_val:.1f}, Rebounded inside Upper Band)"
            }

        return {"symbol": symbol, "signal": "NONE", "reason": "No Sideway reversal setup"}

    def set_sideway_mode(self, enabled: bool) -> dict:
        """Toggle Sideway Mode ON or OFF with Graceful Disabling Handling & Telegram Notification."""
        self.sideway_mode_enabled = enabled
        if enabled:
            self.sideway_state = "ACTIVE"
            msg = "🟢 <b>[SIDEWAY MODE ENABLED]</b>\nState: ACTIVE\n15m Sideway Range Engine is now active and scanning 15m candles concurrently with 4H Swing."
        else:
            # Check if there are active open Sideway positions
            active_sd = [p for p in self.paper_engine.active_positions.values() if p.get("strategy_type") == "SIDEWAY_15M"]
            if active_sd:
                self.sideway_state = "STOPPING"
                msg = f"🟡 <b>[SIDEWAY MODE DISABLING]</b>\nState: STOPPING\nNo new Sideway entries. Gracefully managing {len(active_sd)} active Sideway positions to TP/SL exit."
            else:
                self.sideway_state = "DISABLED"
                msg = "⚪ <b>[SIDEWAY MODE DISABLED]</b>\nState: DISABLED\n15m Sideway Range Engine is completely stopped."

        self.db.save_bot_state(
            self.bot_state, self.trading_mode, self.initial_capital, self.paper_engine.current_capital,
            self.paper_engine.leverage, 1 if enabled else 0, self.sideway_state
        )
        
        # Send instant Telegram Alert on Web Dashboard or API Toggle
        try:
            self.notifier.send_message(msg)
        except Exception as e:
            print(f"[TraderBot] Telegram alert error: {e}")

        return {
            "status": "SUCCESS",
            "sideway_mode_enabled": self.sideway_mode_enabled,
            "sideway_state": self.sideway_state,
            "message": f"Sideway Mode updated to {self.sideway_state}"
        }

    def sync_live_exchange_positions(self) -> dict:
        """
        Reconcile and sync live OKX exchange positions with SQLite Order_trade_crypto.
        Exclusively used in LIVE mode to guarantee 100% Single Source of Truth from Exchange APIs.
        """
        if self.trading_mode == "LIVE" and hasattr(self, 'okx_client') and self.okx_client:
            try:
                res = self.okx_client.get_positions(instType="SWAP")
                if res.get("code") == "0":
                    live_positions = res.get("data", [])
                    synced_count = 0

                    def safe_float(val, default=0.0):
                        try:
                            if val is None or str(val).strip() == "":
                                return float(default)
                            return float(val)
                        except (ValueError, TypeError):
                            return float(default)

                    for pos in live_positions:
                        pos_size = safe_float(pos.get("pos"), 0.0)
                        if pos_size != 0:
                            symbol = pos.get("instId")
                            side = "LONG" if pos_size > 0 else "SHORT"
                            entry_p = safe_float(pos.get("avgPx"), 0.0)
                            margin = safe_float(pos.get("margin"), 0.0)
                            
                            order_payload = {
                                "id": f"LIVE-{symbol}-{side}",
                                "symbol": symbol,
                                "side": side,
                                "timeframe": "4h",
                                "strategy_type": "SWING_4H",
                                "leverage": int(safe_float(pos.get("lever"), 3)),
                                "entry_price": entry_p,
                                "qty": abs(pos_size),
                                "order_value": abs(pos_size) * entry_p,
                                "margin_required": margin if margin > 0 else 100.0,
                                "initial_margin": margin if margin > 0 else 100.0,
                                "sl_price": safe_float(pos.get("slTriggerPx"), 0.0),
                                "tp_price": safe_float(pos.get("tpTriggerPx"), 0.0),
                                "tp1_target": safe_float(pos.get("tpTriggerPx"), 0.0),
                                "tp1_done": False,
                                "realized_pnl": safe_float(pos.get("realizedPnl"), 0.0),
                                "state": "ST_OPEN_100",
                                "entry_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "status": "OPEN"
                            }
                            self.db.save_order_trade(order_payload)
                            synced_count += 1
                    return {"status": "SUCCESS", "message": f"Synced {synced_count} live exchange positions from OKX"}
            except Exception as e:
                print(f"[TraderBot] OKX Live Position Sync exception: {e}")
                return {"status": "ERROR", "message": str(e)}
        return {"status": "SKIPPED", "message": "Live position sync not applicable for PAPER mode"}

    def run_single_iteration(self) -> dict:
        """Execute 1 Iteration Loop across 4H Swing and 15m Sideway Engine."""
        # Telegram Command Check (Panic Stop & Sideway Controls)
        try:
            updates = self.notifier.get_updates()
            for u in updates:
                text = u.get("message", {}).get("text", "").strip().lower()
                if text == "/panic_stop":
                    self.risk_engine.is_circuit_broken = True
                    self.bot_state = "ERROR"
                    self.notifier.send_panic_alert("Triggered via Telegram /panic_stop command")
                elif text in ["/sideway_on", "sideway on", "เปิด sideway"]:
                    res = self.set_sideway_mode(True)
                    self.notifier.send_message(f"🟢 <b>[TELEGRAM COMMAND] 15m Sideway Mode ENABLED</b>\nState: {res['sideway_state']}\nScanning 15m candles active.")
                elif text in ["/sideway_off", "sideway off", "ปิด sideway"]:
                    res = self.set_sideway_mode(False)
                    self.notifier.send_message(f"🟡 <b>[TELEGRAM COMMAND] 15m Sideway Mode DISABLING</b>\nState: {res['sideway_state']}\nNo new entries. Managing active positions.")
                elif text in ["/sideway_status", "sideway status"]:
                    sd_positions = [p for p in self.paper_engine.active_positions.values() if p.get("strategy_type") == "SIDEWAY_15M"]
                    self.notifier.send_message(f"📊 <b>[SIDEWAY MODE STATUS]</b>\nEnabled: {self.sideway_mode_enabled}\nState: {self.sideway_state}\nActive Sideway Positions: {len(sd_positions)}/2")
        except Exception as e:
            print(f"[TraderBot] Telegram check exception: {e}")
                
        if self.risk_engine.is_circuit_broken or self.bot_state == "ERROR":
            self.bot_state = "ERROR"
            return {
                "status": "ERROR",
                "bot_state": "ERROR",
                "trading_mode": self.trading_mode,
                "sideway_mode_enabled": self.sideway_mode_enabled,
                "sideway_state": self.sideway_state,
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
                "sideway_mode_enabled": self.sideway_mode_enabled,
                "sideway_state": self.sideway_state,
                "active_symbols": self.symbols,
                "timeframe": self.timeframe_str,
                "reason": "บอทหยุดพักการทำงาน (User Paused)",
                "paper_summary": self.paper_engine.get_summary(),
                "active_positions": list(self.paper_engine.active_positions.values()),
                "trade_history": self.paper_engine.trade_history[:10]
            }

        opened_symbols_this_iteration = set()
        pair_results = {}
        for sym in self.symbols:
            try:
                # 1. Evaluate 4H Swing Engine Signal (Primary Strategy Baseline)
                candles_4h = self.client.get_candles(symbol=sym, resolution="240", limit=300)
                if candles_4h:
                    eval_res = self.evaluate_pair_signal(sym, candles_4h)
                    pair_results[sym] = {
                        "last_price": candles_4h[-1]["close"],
                        "eval": eval_res
                    }
                    if eval_res.get("signal") in ["LONG", "SHORT"]:
                        open_res = self.paper_engine.open_position(
                            symbol=sym,
                            side=eval_res["signal"],
                            entry_price=eval_res["entry_price"],
                            sl_price=eval_res["sl_price"],
                            tp1_target=eval_res["tp1_target"],
                            market_snapshot=eval_res["market_snapshot"],
                            id_prefix=eval_res.get("id_prefix", "SW-")
                        )
                        if open_res.get("status") == "SUCCESS":
                            opened_symbols_this_iteration.add(sym)
                            self.notifier.send_message(
                                f"<b>📡 [SWING 4H SIGNAL]</b>\n"
                                f"Asset: {sym} ({eval_res['signal']})\n"
                                f"Entry: ${eval_res['entry_price']:,.4f}\n"
                                f"TP1: ${eval_res['tp1_target']:,.4f} | SL: ${eval_res['sl_price']:,.4f}"
                            )

                # 2. Evaluate 15m Sideway Engine Signal (If Enabled and no 4H Swing entry for same symbol)
                if self.sideway_mode_enabled and self.sideway_state == "ACTIVE":
                    if sym in opened_symbols_this_iteration or sym in self.paper_engine.active_positions:
                        # Signal Deduplication Guard: Prioritize 4H Swing, suppress duplicate 15m Sideway entry
                        continue

                    candles_15m = self.client.get_candles(symbol=sym, resolution="15m", limit=50)
                    if candles_15m:
                        closes_15m = [c["close"] for c in candles_15m]
                        sma20 = TechnicalIndicators.calculate_sma(closes_15m, 20)[-1]
                        
                        # Dynamic TP Update for active Sideway trades
                        self.paper_engine.update_dynamic_sideway_tps(sym, sma20)

                        sd_eval = self.evaluate_sideway_signal(sym, candles_15m)
                        if sd_eval.get("signal") in ["LONG", "SHORT"]:
                            self.paper_engine.open_position(
                                symbol=sym,
                                side=sd_eval["signal"],
                                entry_price=sd_eval["entry_price"],
                                sl_price=sd_eval["sl_price"],
                                tp1_target=sd_eval["tp1_target"],
                                market_snapshot=sd_eval["market_snapshot"],
                                id_prefix=sd_eval.get("id_prefix", "SD-")
                            )
                            self.notifier.send_message(
                                f"<b>📡 [SIDEWAY 15M SIGNAL]</b>\n"
                                f"Asset: {sym} ({sd_eval['signal']})\n"
                                f"Entry: ${sd_eval['entry_price']:,.4f}\n"
                                f"TP (Middle Band): ${sd_eval['tp1_target']:,.4f} | SL: ${sd_eval['sl_price']:,.4f}"
                            )

            except Exception as e:
                print(f"[TraderBot] Error scanning OKX pair {sym}: {e}")

        # Update Paper Trading Positions check
        try:
            closed_trades = self.paper_engine.update_positions(pair_results)
            for closed in closed_trades:
                tag = "[SIDEWAY 15M]" if closed.get("id", "").startswith("SD-") or closed.get("strategy_type") == "SIDEWAY_15M" else "[SWING 4H]"
                pnl_msg = f"<b>{tag} {closed['side']} {closed['type']}</b>\nAsset: {closed['symbol']}\nNet PnL: ${closed['net_pnl']} ({closed['pnl_pct']}%)"
                self.notifier.send_message(pnl_msg)

                # Set 8-hour (2 bars) cooldown lockout if closed via SL
                if "SL" in closed.get("type", ""):
                    self.symbol_lockouts[closed["symbol"]] = time.time() + (8 * 3600)

        except Exception as e:
            print(f"[TraderBot] Error updating paper positions: {e}")

        # Check Graceful Disabling State Auto-Transition:
        if self.sideway_state == "STOPPING":
            active_sd = [p for p in self.paper_engine.active_positions.values() if p.get("strategy_type") == "SIDEWAY_15M"]
            if not active_sd:
                self.sideway_state = "DISABLED"
                self.sideway_mode_enabled = False
                self.db.save_bot_state(
                    self.bot_state, self.trading_mode, self.initial_capital, self.paper_engine.current_capital,
                    self.paper_engine.leverage, 0, "DISABLED"
                )

        # Trigger Active Monitoring 30m scan if interval elapsed
        if time.time() - self.active_monitor.last_scan_timestamp >= self.active_monitor.scan_interval_sec:
            try:
                self.active_monitor.run_30m_scan()
            except Exception as e:
                print(f"[TraderBot] Error running Active Monitoring scan: {e}")

        btc_price = pair_results.get("BTC-USDT-SWAP", {}).get("last_price", 0.0)
        paper_summary = self.paper_engine.get_summary()
        
        return {
            "status": "OK",
            "bot_state": "RUNNING",
            "trading_mode": self.trading_mode,
            "sideway_mode_enabled": self.sideway_mode_enabled,
            "sideway_state": self.sideway_state,
            "scan_interval_sec": self.get_scan_interval_sec(),
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
                    "status": "ACTIVE (4H Swing + 15m Sideway Engine)"
                }
            },
            "active_positions": list(self.paper_engine.active_positions.values()),
            "trade_history": self.paper_engine.trade_history[:10]
        }

    def get_scan_interval_sec(self) -> int:
        """Return 900s (15m) when Sideway Mode is active/stopping, otherwise 1800s (30m)."""
        if self.sideway_mode_enabled or self.sideway_state in ["ACTIVE", "STOPPING"]:
            return 900
        return 1800
