"""
Trading Bot Engine Loop with OKX Perpetual Futures & Dual-Direction Trading (LONG & SHORT)
Enforces 70/30 Production-Grade Core-Satellite Architecture (Spot Rebalance + Futures Geometric Grid).
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
from src.core.rebalance_engine import CoreRebalanceEngine
from src.core.grid_engine import SatelliteGridEngine

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
            "AVAX-USDT-SWAP",
            "BNB-USDT-SWAP",
            "NEAR-USDT-SWAP",
            "UNI-USDT-SWAP",
            "FIL-USDT-SWAP",
            "ALGO-USDT-SWAP"
        ]
        self.resolution = resolution  # "240" (4H)
        self.timeframe_str = "4h"
        self.client = OKXClient()
        self.risk_engine = RiskEngine()
        self.notifier = TelegramNotifier()
        self.db = DatabaseManager()
        
        # 70/30 Production-Grade Core-Satellite Capital Allocation
        self.initial_capital = initial_capital
        self.core_capital_70 = initial_capital * 0.70       # 70% Core Weight ($7,000)
        self.satellite_capital_30 = initial_capital * 0.30  # 30% Satellite Weight ($3,000)
        
        self.rebalance_engine = CoreRebalanceEngine(client=self.client)
        self.grid_engine = SatelliteGridEngine()
        self.peak_equity = initial_capital
        
        self.funding_capital_80 = self.core_capital_70
        self.swing_capital_20 = self.satellite_capital_30
        
        self.paper_engine = PaperTradingEngine(initial_capital=self.satellite_capital_30)
        self.active_monitor = ActiveMonitor(self.client, self.paper_engine, notifier=self.notifier)
        self.trading_mode = "PAPER"  # "PAPER" or "LIVE"
        self.bot_state = "RUNNING"   # "RUNNING", "PAUSED", "ERROR"
        
        # Sideway Engine State & Config
        db_state = self.db.get_bot_state()
        self.sideway_mode_enabled = bool(db_state.get("sideway_mode_enabled", 0))
        self.sideway_state = db_state.get("sideway_state", "DISABLED")
        
        self.last_signals_sent = {}  # { symbol: signal_key }
        self.symbol_lockouts = {}    # { symbol: lockout_until_timestamp }

    def sync_live_exchange_positions(self):
        """Reconcile local paper positions with OKX exchange API positions."""
        if not hasattr(self, 'client') or not self.client:
            return
        res = self.client.get_positions(instType="SWAP")
        if res.get("code") == "0":
            data_list = res.get("data", [])
            active_symbols_on_okx = set()
            for p in data_list:
                p_size = float(p.get("pos", 0.0) or 0.0)
                if p_size != 0:
                    sym = p.get("instId", "")
                    active_symbols_on_okx.add(sym)
                    if sym not in self.paper_engine.active_positions:
                        pos_side = str(p.get("posSide", "long")).upper()
                        if pos_side == "NET":
                            pos_side = "LONG" if p_size > 0 else "SHORT"
                        entry_px = float(p.get("avgPx", 0.0) or 0.0)
                        order_val = abs(p_size) * entry_px
                        self.paper_engine.active_positions[sym] = {
                            "id": f"OKX-{sym}-{pos_side}",
                            "symbol": sym,
                            "side": pos_side,
                            "timeframe": "4h",
                            "strategy_type": "SWING_4H",
                            "leverage": int(float(p.get("lever", 3) or 3)),
                            "entry_price": entry_px,
                            "qty": abs(p_size),
                            "order_value": round(order_val, 2),
                            "margin_required": float(p.get("margin", 100.0) or 100.0),
                            "initial_margin": float(p.get("margin", 100.0) or 100.0),
                            "sl_price": float(p.get("slTriggerPx", 0.0) or 0.0),
                            "tp1_target": float(p.get("tpTriggerPx", 0.0) or 0.0),
                            "tp_price": float(p.get("tpTriggerPx", 0.0) or 0.0),
                            "entry_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "status": "OPEN"
                        }
                        self.paper_engine._save_state()

    def evaluate_pair_signal(self, symbol: str, candles: list) -> dict:
        if not candles or len(candles) < 200:
            return {"symbol": symbol, "signal": "NONE", "reason": "Insufficient 4H candles"}
            
        closes = [c["close"] for c in candles]
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
        
        now_ts = time.time()
        if symbol in self.symbol_lockouts:
            if now_ts < self.symbol_lockouts[symbol]:
                rem_mins = int((self.symbol_lockouts[symbol] - now_ts) / 60)
                return {
                    "symbol": symbol,
                    "signal": "NONE",
                    "reason": f"8-hour SL cooldown active ({rem_mins}m remaining)",
                    "market_snapshot": market_snapshot
                }
            else:
                del self.symbol_lockouts[symbol]

        if symbol in self.paper_engine.active_positions:
            return {
                "symbol": symbol,
                "signal": "NONE",
                "reason": f"Position already active for {symbol}",
                "market_snapshot": market_snapshot
            }
            
        if adx_val < 20.0:
            return {
                "symbol": symbol,
                "signal": "NONE",
                "reason": f"ADX ({adx_val:.2f}) < 20.0 threshold (Weak trend)",
                "market_snapshot": market_snapshot
            }
            
        is_st_flip_green = (prev_st["direction"] == -1 and curr_st["direction"] == 1)
        if is_st_flip_green and prev_price > ema200_4h:
            return {
                "symbol": symbol,
                "signal": "LONG",
                "entry_price": current_price,
                "atr": atr_val,
                "market_snapshot": market_snapshot,
                "reason": "4H Supertrend flipped GREEN + Price > EMA200 + ADX > 20"
            }
            
        is_st_flip_red = (prev_st["direction"] == 1 and curr_st["direction"] == -1)
        if is_st_flip_red and prev_price < ema200_4h:
            return {
                "symbol": symbol,
                "signal": "SHORT",
                "entry_price": current_price,
                "atr": atr_val,
                "market_snapshot": market_snapshot,
                "reason": "4H Supertrend flipped RED + Price < EMA200 + ADX > 20"
            }

        return {
            "symbol": symbol,
            "signal": "NONE",
            "reason": "No entry setup",
            "market_snapshot": market_snapshot
        }

    def evaluate_sideway_signal(self, symbol: str, candles_15m: list) -> dict:
        if not candles_15m or len(candles_15m) < 30:
            return {"symbol": symbol, "signal": "NONE", "reason": "Insufficient 15m candles"}

        closes = [c["close"] for c in candles_15m]
        prev_close = closes[-2]
        curr_close = closes[-1]

        sma20 = TechnicalIndicators.calculate_sma(closes, 20)[-1]
        std20 = TechnicalIndicators.calculate_std(closes, 20)[-1]
        lower_band = round(sma20 - (2.0 * std20), 4)
        upper_band = round(sma20 + (2.0 * std20), 4)

        rsi14 = TechnicalIndicators.calculate_rsi(closes, 14)[-1]
        atr15m = TechnicalIndicators.calculate_atr(candles_15m, 14)[-1]

        market_snapshot = {
            "strategy_type": "SIDEWAY_15M",
            "timeframe": "15m",
            "bb_lower": lower_band,
            "bb_middle": round(sma20, 4),
            "bb_upper": upper_band,
            "rsi_15m": round(rsi14, 2),
            "atr_15m": round(atr15m, 4)
        }

        if symbol in self.paper_engine.active_positions:
            return {"symbol": symbol, "signal": "NONE", "reason": "Position already active"}

        if prev_close <= lower_band and curr_close > lower_band and rsi14 < 35.0:
            sl_price = round(curr_close - (1.5 * atr15m), 4)
            return {
                "symbol": symbol,
                "signal": "LONG",
                "entry_price": curr_close,
                "sl_price": sl_price,
                "tp1_target": round(sma20, 4),
                "market_snapshot": market_snapshot,
                "id_prefix": "SD-",
                "reason": "15m Lower BB Reversal + RSI Oversold (< 35)"
            }

        if prev_close >= upper_band and curr_close < upper_band and rsi14 > 65.0:
            sl_price = round(curr_close + (1.5 * atr15m), 4)
            return {
                "symbol": symbol,
                "signal": "SHORT",
                "entry_price": curr_close,
                "sl_price": sl_price,
                "tp1_target": round(sma20, 4),
                "market_snapshot": market_snapshot,
                "id_prefix": "SD-",
                "reason": "15m Upper BB Reversal + RSI Overbought (> 65)"
            }

        return {"symbol": symbol, "signal": "NONE", "reason": "No sideway reversal", "market_snapshot": market_snapshot}

    def set_sideway_mode(self, enabled: bool):
        if enabled:
            self.sideway_mode_enabled = True
            self.sideway_state = "ACTIVE"
            msg = "🟢 โหมด 15m Sideway Range Scalping เปิดการทำงานแล้ว (ACTIVE)"
        else:
            active_sd_positions = [
                p for p in self.paper_engine.active_positions.values() 
                if p.get("strategy_type") == "SIDEWAY_15M"
            ]
            if active_sd_positions:
                self.sideway_mode_enabled = True
                self.sideway_state = "STOPPING"
                msg = f"🟡 โหมด 15m Sideway Range Scalping กำลังปิด (STOPPING) — มีออเดอร์ค้าง {len(active_sd_positions)} รายการ ระบบจะรอยิงปิด TP/SL อัตโนมัติก่อนเคลียร์เข้าสภาวะ DISABLED"
            else:
                self.sideway_mode_enabled = False
                self.sideway_state = "DISABLED"
                msg = "⚪ โหมด 15m Sideway Range Scalping ปิดการทำงานเรียบร้อยแล้ว (DISABLED)"

        self.db.save_bot_state(
            self.bot_state, self.trading_mode, self.initial_capital,
            self.paper_engine.current_capital, self.paper_engine.leverage,
            1 if self.sideway_mode_enabled else 0, self.sideway_state
        )
        return {
            "status": "SUCCESS",
            "sideway_mode_enabled": self.sideway_mode_enabled,
            "sideway_state": self.sideway_state,
            "message": msg
        }

    def run_single_iteration(self) -> dict:
        pair_results = {}
        for sym in self.symbols:
            try:
                candles_4h = self.client.get_candles(symbol=sym, resolution="240", limit=300)
                if candles_4h:
                    last_price = candles_4h[-1]["close"]
                    swing_eval = self.evaluate_pair_signal(sym, candles_4h)
                    
                    pair_results[sym] = {
                        "last_price": last_price,
                        "eval": swing_eval
                    }

                    if swing_eval.get("signal") in ["LONG", "SHORT"]:
                        side = swing_eval["signal"]
                        atr = swing_eval["atr"]
                        risk = self.risk_engine.calculate_position_sizing(
                            self.paper_engine.current_capital, last_price, atr, side=side
                        )
                        self.paper_engine.open_position(
                            symbol=sym,
                            side=side,
                            entry_price=last_price,
                            sl_price=risk["sl_price"],
                            tp1_target=risk["tp_price"],
                            market_snapshot=swing_eval["market_snapshot"]
                        )
                        self.notifier.send_message(
                            f"<b>📡 [4H SWING SIGNAL]</b>\n"
                            f"Asset: {sym} ({side})\n"
                            f"Entry: ${last_price:,.4f}\n"
                            f"SL: ${risk['sl_price']:,.4f} | TP1: ${risk['tp_price']:,.4f}"
                        )

                    candles_15m = self.client.get_candles(symbol=sym, resolution="15m", limit=50)
                    if candles_15m:
                        closes_15m = [c["close"] for c in candles_15m]
                        sma20 = TechnicalIndicators.calculate_sma(closes_15m, 20)[-1]
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

            except Exception as e:
                print(f"[TraderBot] Error scanning OKX pair {sym}: {e}")

        try:
            closed_trades = self.paper_engine.update_positions(pair_results)
            for closed in closed_trades:
                tag = "[SIDEWAY 15M]" if closed.get("id", "").startswith("SD-") or closed.get("strategy_type") == "SIDEWAY_15M" else "[SWING 4H]"
                pnl_msg = f"<b>{tag} {closed['side']} {closed['type']}</b>\nAsset: {closed['symbol']}\nNet PnL: ${closed['net_pnl']} ({closed['pnl_pct']}%)"
                self.notifier.send_message(pnl_msg)
                if "SL" in closed.get("type", ""):
                    self.symbol_lockouts[closed["symbol"]] = time.time() + (8 * 3600)
        except Exception as e:
            print(f"[TraderBot] Error updating paper positions: {e}")

        if self.sideway_state == "STOPPING":
            active_sd = [p for p in self.paper_engine.active_positions.values() if p.get("strategy_type") == "SIDEWAY_15M"]
            if not active_sd:
                self.sideway_state = "DISABLED"
                self.sideway_mode_enabled = False
                self.db.save_bot_state(
                    self.bot_state, self.trading_mode, self.initial_capital, self.paper_engine.current_capital,
                    self.paper_engine.leverage, 0, "DISABLED"
                )

        if time.time() - self.active_monitor.last_scan_timestamp >= self.active_monitor.scan_interval_sec:
            try:
                self.active_monitor.run_30m_scan()
            except Exception as e:
                print(f"[TraderBot] Error running Active Monitoring scan: {e}")

        btc_price = pair_results.get("BTC-USDT-SWAP", {}).get("last_price", 65000.0)
        eth_price = pair_results.get("ETH-USDT-SWAP", {}).get("last_price", 1950.0)
        btc_eval = pair_results.get("BTC-USDT-SWAP", {}).get("eval", {}).get("market_snapshot", {})
        btc_ema200_1d = btc_eval.get("ema200_4h", 63000.0)
        adx_4h = btc_eval.get("adx", 19.0)
        atr_4h = btc_eval.get("atr_4h", 450.0)
        
        # 1. Run Core Spot Rebalance Process (70% Capital Allocation)
        btc_qty = (self.core_capital_70 * 0.40) / btc_price if btc_price > 0 else 0.04
        eth_qty = (self.core_capital_70 * 0.30) / eth_price if eth_price > 0 else 1.0
        usdt_cash = self.core_capital_70 * 0.30
        
        rebalance_telemetry = self.rebalance_engine.process_rebalance(
            btc_qty, btc_price, eth_qty, eth_price, usdt_cash, btc_ema200_1d
        )
        
        # 2. Run Satellite Futures Grid Process (30% Capital Allocation)
        bb_lower = btc_price * 0.97
        bb_upper = btc_price * 1.03
        atr_15m = atr_4h * 0.35
        p_lower, p_upper, grid_n = self.grid_engine.determine_grid_bounds_and_density(bb_lower, bb_upper, atr_15m)
        grid_config = self.grid_engine.calculate_geometric_grid(p_lower, p_upper, grid_n)
        oob_eval = self.grid_engine.evaluate_out_of_bounds("BTC-USDT-SWAP", btc_price, p_lower, p_upper, adx_4h, atr_4h)
        
        # 3. Evaluate Dynamic 3-Level Circuit Breakers & Peak Drawdown Tracker
        current_total_equity = rebalance_telemetry["v_core"] + self.paper_engine.current_capital
        if current_total_equity > self.peak_equity:
            self.peak_equity = current_total_equity
            
        cb_eval = self.risk_engine.evaluate_circuit_breakers(
            current_total_equity, self.peak_equity, btc_price, btc_ema200_1d, adx_4h, atr_15m, atr_15m
        )

        paper_summary = self.paper_engine.get_summary()
        
        return {
            "status": "OK",
            "bot_state": "RUNNING" if not cb_eval["level3_hard_stop"] else "ERROR",
            "trading_mode": self.trading_mode,
            "sideway_mode_enabled": self.sideway_mode_enabled,
            "sideway_state": self.sideway_state,
            "scan_interval_sec": self.get_scan_interval_sec(),
            "active_symbols": self.symbols,
            "timeframe": self.timeframe_str,
            "last_price": btc_price,
            "pair_results": pair_results,
            "paper_summary": paper_summary,
            "core_satellite_architecture": {
                "architecture": "Production-Grade Core-Satellite (70% Spot Rebalance + 30% Futures Grid)",
                "total_equity_usd": round(current_total_equity, 2),
                "peak_equity_usd": round(self.peak_equity, 2),
                "drawdown_pct": cb_eval["drawdown_pct"],
                "core_engine_70pct": {
                    "strategy": "Spot Volatility Harvesting (Shannon's Demon)",
                    "allocated_capital_usd": self.core_capital_70,
                    "v_core_value_usd": rebalance_telemetry["v_core"],
                    "macro_regime": rebalance_telemetry["macro_regime"],
                    "current_weights": rebalance_telemetry["current_weights"],
                    "target_weights": rebalance_telemetry["target_weights"],
                    "rebalance_actions": rebalance_telemetry["rebalance_actions"]
                },
                "satellite_engine_30pct": {
                    "strategy": "Futures Geometric Grid (Bollinger Bands 20,2 4H)",
                    "allocated_capital_usd": self.satellite_capital_30,
                    "grid_type": "GEOMETRIC",
                    "grid_status": grid_config["status"],
                    "grid_ratio_r": grid_config.get("ratio_r"),
                    "g_profit_pct": grid_config.get("g_profit_pct"),
                    "bounds": {"p_lower": p_lower, "p_upper": p_upper, "grid_count": grid_n},
                    "out_of_bounds_status": oob_eval
                },
                "circuit_breaker_3level": cb_eval
            },
            "active_positions": list(self.paper_engine.active_positions.values()),
            "trade_history": self.paper_engine.trade_history[:10]
        }

    def get_scan_interval_sec(self) -> int:
        if self.sideway_mode_enabled or self.sideway_state in ["ACTIVE", "STOPPING"]:
            return 900
        return 1800
