"""
Trading Bot Engine Loop with OKX Perpetual Futures & 15m Range Scalping (Zone Touch + RSI)
Enforces 70/30 Enterprise Core-Satellite Architecture (Spot Rebalance + 15m Scalping Grid).
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
        self.timeframe_str = "15m"
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
        
        # 15m Range Scalping Engine State (Default ACTIVE)
        self.sideway_mode_enabled = True
        self.sideway_state = "ACTIVE"
        
        self.last_signals_sent = {}  # { symbol: signal_key }
        self.symbol_lockouts = {}    # { symbol: lockout_until_timestamp }

    def sync_live_exchange_positions(self):
        """Reconcile local paper positions with OKX exchange API positions (100% Bi-Directional Synchronization)."""
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
                            "timeframe": "15m",
                            "strategy_type": "SIDEWAY_15M",
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

            # Purge closed positions that are no longer active on OKX
            local_keys = list(self.paper_engine.active_positions.keys())
            for key in local_keys:
                pos = self.paper_engine.active_positions[key]
                sym = pos.get("symbol", key)
                if sym not in active_symbols_on_okx:
                    print(f"[TraderBot Sync] Purging closed position for {sym} (No longer active on OKX exchange)")
                    del self.paper_engine.active_positions[key]
                    if sym in self.active_monitor.last_sent_recommendations:
                        del self.active_monitor.last_sent_recommendations[sym]
                    if sym in self.active_monitor.last_sent_timestamps:
                        del self.active_monitor.last_sent_timestamps[sym]
                    self.paper_engine._save_state()

    def evaluate_sideway_signal(self, symbol: str, candles_15m: list) -> dict:
        """
        15m Scalping Engine (Zone Touch & RSI Trigger):
        - LONG: Current Price <= Lower Band * 1.001 AND RSI(14) < 42.0
        - SHORT: Current Price >= Upper Band * 0.999 AND RSI(14) > 58.0
        - Dynamic TP Target: 15m SMA20 (Middle Band)
        """
        if not candles_15m or len(candles_15m) < 30:
            return {"symbol": symbol, "signal": "NONE", "reason": "Insufficient 15m candles"}

        if not self.sideway_mode_enabled or self.sideway_state == "STOPPING":
            return {"symbol": symbol, "signal": "NONE", "reason": "Sideway Engine OFF or Stopping"}

        active_sideway_positions = [
            p for p in self.paper_engine.active_positions.values() 
            if p.get("strategy_type") == "SIDEWAY_15M"
        ]
        total_sideway_margin = sum(p.get("margin_required", 0) for p in active_sideway_positions)
        if len(active_sideway_positions) >= 4 or total_sideway_margin >= 600.0:
            return {"symbol": symbol, "signal": "NONE", "reason": "Sideway Capital Quota Full ($600 Margin / Max 4 Positions)"}

        if symbol in self.paper_engine.active_positions:
            return {"symbol": symbol, "signal": "NONE", "reason": f"Position already active for {symbol}"}

        closes = [c["close"] for c in candles_15m]

        adx_list = TechnicalIndicators.calculate_adx(candles_15m, 14)
        adx_val = adx_list[-1] if adx_list else 20.0

        if adx_val >= 30.0:
            return {"symbol": symbol, "signal": "NONE", "reason": f"ADX too high ({adx_val:.1f} >= 30.0) - Strong Trend Detected"}

        rsi_list = TechnicalIndicators.calculate_rsi(closes, 14)
        rsi_val = rsi_list[-1] if rsi_list else 50.0

        atr_val = TechnicalIndicators.calculate_atr(candles_15m, 14)[-1]

        sma20 = TechnicalIndicators.calculate_sma(closes, 20)
        sma20_curr = sma20[-1]
        
        recent20 = closes[-20:]
        mean20 = sum(recent20) / 20
        variance20 = sum((x - mean20) ** 2 for x in recent20) / 20
        std20 = math.sqrt(variance20)
        upper_band = sma20_curr + (2.0 * std20)
        lower_band = sma20_curr - (2.0 * std20)

        curr_close = closes[-1]

        is_long_touch = (curr_close <= lower_band * 1.001) and (rsi_val < 42.0)
        is_short_touch = (curr_close >= upper_band * 0.999) and (rsi_val > 58.0)

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

        if is_long_touch:
            tp_price = round(sma20_curr, 4)
            sl_price = round(curr_close - (1.5 * atr_val), 4)
            return {
                "symbol": symbol,
                "signal": "LONG",
                "entry_price": curr_close,
                "sl_price": sl_price,
                "tp1_target": tp_price,
                "market_snapshot": market_snapshot,
                "id_prefix": "SD-",
                "reason": f"15m BB Lower Zone Touch + RSI ({rsi_val:.1f} < 42.0)"
            }

        if is_short_touch:
            tp_price = round(sma20_curr, 4)
            sl_price = round(curr_close + (1.5 * atr_val), 4)
            return {
                "symbol": symbol,
                "signal": "SHORT",
                "entry_price": curr_close,
                "sl_price": sl_price,
                "tp1_target": tp_price,
                "market_snapshot": market_snapshot,
                "id_prefix": "SD-",
                "reason": f"15m BB Upper Zone Touch + RSI ({rsi_val:.1f} > 58.0)"
            }

        return {"symbol": symbol, "signal": "NONE", "reason": "No zone touch", "market_snapshot": market_snapshot}

    def run_single_iteration(self) -> dict:
        opened_symbols_this_iteration = set()
        pair_results = {}
        for sym in self.symbols:
            try:
                # 1. Primary Strategy: 15m Range Scalping Engine (Zone Touch & RSI Trigger)
                candles_15m = self.client.get_candles(symbol=sym, resolution="15m", limit=50)
                if candles_15m:
                    last_price = candles_15m[-1]["close"]
                    closes_15m = [c["close"] for c in candles_15m]
                    sma20 = TechnicalIndicators.calculate_sma(closes_15m, 20)[-1]
                    
                    # Dynamic TP Update for active Sideway trades
                    self.paper_engine.update_dynamic_sideway_tps(sym, sma20)

                    sd_eval = self.evaluate_sideway_signal(sym, candles_15m)
                    pair_results[sym] = {
                        "last_price": last_price,
                        "eval": sd_eval
                    }

                    if self.sideway_mode_enabled and self.sideway_state == "ACTIVE":
                        if sym not in opened_symbols_this_iteration and sym not in self.paper_engine.active_positions:
                            if sd_eval.get("signal") in ["LONG", "SHORT"]:
                                side = sd_eval["signal"]
                                # 1. Submit REAL order directly to OKX Demo API
                                okx_sd_res = self.client.place_market_order(
                                    symbol=sym,
                                    side=side,
                                    sz=1.0,
                                    sl_price=sd_eval["sl_price"],
                                    tp_price=sd_eval["tp1_target"]
                                )
                                self.paper_engine.open_position(
                                    symbol=sym,
                                    side=side,
                                    entry_price=sd_eval["entry_price"],
                                    sl_price=sd_eval["sl_price"],
                                    tp1_target=sd_eval["tp1_target"],
                                    market_snapshot=sd_eval["market_snapshot"],
                                    id_prefix=sd_eval.get("id_prefix", "SD-")
                                )
                                opened_symbols_this_iteration.add(sym)
                                self.notifier.send_message(
                                    f"<b>🚀 [OKX SCALPING 15M ORDER PLACED]</b>\n"
                                    f"Asset: <b>{sym}</b> ({side})\n"
                                    f"Entry Price: ${sd_eval['entry_price']:,.4f}\n"
                                    f"TP Target: ${sd_eval['tp1_target']:,.4f} | SL: ${sd_eval['sl_price']:,.4f}\n"
                                    f"OKX Status: {okx_sd_res.get('status')}"
                                )

            except Exception as e:
                print(f"[TraderBot] Error scanning OKX pair {sym}: {e}")

        # Update and Check Take Profit / Stop Loss triggers
        try:
            # Auto-close on OKX exchange when TP or SL is touched
            for sym, pos in list(self.paper_engine.active_positions.items()):
                curr_item = pair_results.get(sym, {})
                curr_p = curr_item.get("last_price")
                if not curr_p:
                    continue
                pos_side = pos.get("side", "LONG")
                tp_target = pos.get("tp1_target", pos.get("tp_price", 0.0))
                sl_target = pos.get("sl_price", 0.0)
                
                hit_tp = (curr_p >= tp_target if pos_side == "LONG" else curr_p <= tp_target) if tp_target > 0 else False
                hit_sl = (curr_p <= sl_target if pos_side == "LONG" else curr_p >= sl_target) if sl_target > 0 else False
                
                if hit_tp or hit_sl:
                    close_tag = "TAKE PROFIT (TP)" if hit_tp else "STOP LOSS (SL)"
                    # Send Close order to OKX Exchange
                    self.client.close_position_on_okx(sym, pos_side, td_mode="cross")
                    
                    pnl_val = (curr_p - pos["entry_price"]) * pos["qty"] if pos_side == "LONG" else (pos["entry_price"] - curr_p) * pos["qty"]
                    pnl_pct = (pnl_val / pos.get("margin_required", 100.0)) * 100.0
                    
                    now_struct = time.localtime()
                    trade_rec = {
                        "id": f"SCALP-EXIT-{sym}-{int(time.time())}",
                        "symbol": sym,
                        "side": pos_side,
                        "type": f"{pos_side} {close_tag}",
                        "timeframe": "15m",
                        "strategy_type": "SIDEWAY_15M",
                        "leverage": pos.get("leverage", 3),
                        "entry_price": pos["entry_price"],
                        "exit_price": curr_p,
                        "qty": pos["qty"],
                        "net_pnl": round(pnl_val, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "holding_duration_formatted": "15m Scalp",
                        "entry_time": pos.get("entry_time", time.strftime("%Y-%m-%d %H:%M:%S", now_struct)),
                        "exit_time": time.strftime("%Y-%m-%d %H:%M:%S", now_struct),
                        "day_of_week": time.strftime("%A", now_struct),
                        "hour_of_day": now_struct.tm_hour
                    }
                    self.paper_engine.trade_history.insert(0, trade_rec)
                    if sym in self.paper_engine.active_positions:
                        del self.paper_engine.active_positions[sym]
                    self.paper_engine._save_state()
                    
                    self.notifier.send_message(
                        f"<b>🎯 [15M SCALPING {close_tag} EXECUTED]</b>\n"
                        f"Asset: <b>{sym}</b> ({pos_side})\n"
                        f"Exit Price: ${curr_p:,.4f}\n"
                        f"Net PnL: <b>${pnl_val:,.2f} USD ({pnl_pct:+.2f}%)</b>"
                    )

        except Exception as e:
            print(f"[TraderBot] Error updating 15m scalping positions: {e}")

        btc_price = pair_results.get("BTC-USDT-SWAP", {}).get("last_price", 64000.0)
        eth_price = pair_results.get("ETH-USDT-SWAP", {}).get("last_price", 1900.0)
        btc_eval = pair_results.get("BTC-USDT-SWAP", {}).get("eval", {}).get("market_snapshot", {})
        btc_ema200_1d = btc_eval.get("ema200_4h", 63000.0)
        adx_4h = btc_eval.get("adx", 19.0)
        atr_15m = btc_eval.get("atr_15m", 140.0)
        
        # 1. Run Core Spot Rebalance Process (70% Capital Allocation)
        btc_qty = (self.core_capital_70 * 0.40) / btc_price if btc_price > 0 else 0.04
        eth_qty = (self.core_capital_70 * 0.30) / eth_price if eth_price > 0 else 1.0
        usdt_cash = self.core_capital_70 * 0.30
        
        rebalance_telemetry = self.rebalance_engine.process_rebalance(
            btc_qty, btc_price, eth_qty, eth_price, usdt_cash, btc_ema200_1d
        )
        
        # Send Spot Rebalance Telegram Notification ONLY if executed successfully on OKX
        for act in rebalance_telemetry.get("rebalance_actions", []):
            if act.get("triggered"):
                spot_res = act.get("twap_execution", {}).get("spot_order_res", {})
                if spot_res and spot_res.get("status") == "SUCCESS":
                    self.notifier.send_message(
                        f"<b>⚖️ [OKX SPOT REBALANCE EXECUTED]</b>\n"
                        f"Asset: <b>{act.get('asset')}/USDT (Spot)</b>\n"
                        f"Action: <b>{act.get('action')}</b>\n"
                        f"Trade Qty: {act.get('trade_qty')} (${abs(act.get('val_diff', 0)):,.2f} USD)\n"
                        f"Weight Drift: {act.get('weight_drift', 0)*100:.2f}%\n"
                        f"Macro Regime: {rebalance_telemetry.get('macro_regime')}\n"
                        f"OKX Order ID: {spot_res.get('order_id', 'N/A')}\n"
                        f"OKX Spot Status: <b>SUCCESS 🟢</b>"
                    )
        
        # 2. Run Satellite Futures Grid Process (30% Capital Allocation)
        bb_lower = btc_price * 0.97
        bb_upper = btc_price * 1.03
        p_lower, p_upper, grid_n = self.grid_engine.determine_grid_bounds_and_density(bb_lower, bb_upper, atr_15m)
        grid_config = self.grid_engine.calculate_geometric_grid(p_lower, p_upper, grid_n)
        oob_eval = self.grid_engine.evaluate_out_of_bounds("BTC-USDT-SWAP", btc_price, p_lower, p_upper, adx_4h, atr_15m)
        
        fr_data = self.client.get_funding_rate("BTC-USDT-SWAP") if hasattr(self.client, 'get_funding_rate') else {}
        funding_rate = fr_data.get("funding_rate", 0.0001)
        funding_eval = self.grid_engine.evaluate_funding_rate_guard(funding_rate)
        
        # 3. Circuit Breaker & Monitoring Telemetry
        current_total_equity = rebalance_telemetry["v_core"] + self.paper_engine.current_capital
        safe_peak = max(current_total_equity, self.peak_equity if self.peak_equity is not None else 0.0)
        self.peak_equity = safe_peak
            
        cb_eval = self.risk_engine.evaluate_circuit_breakers(
            current_total_equity, self.peak_equity, btc_price, btc_ema200_1d, adx_4h, atr_15m, atr_15m
        )

        active_monitor_telemetry = self.active_monitor.evaluate_multi_timeframe_matrix(
            btc_price, current_total_equity, safe_peak, adx_4h, atr_15m, atr_15m, btc_ema200_1d, funding_rate
        )

        self.active_monitor.send_position_monitoring_telemetry(list(self.paper_engine.active_positions.values()), pair_results)

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
                "architecture": "Enterprise Core-Satellite Strategy (70% Spot Rebalance + 30% Futures 15m Scalping Grid)",
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
                    "strategy": "15m Range Scalping & Geometric Grid",
                    "allocated_capital_usd": self.satellite_capital_30,
                    "grid_type": "GEOMETRIC",
                    "grid_status": grid_config["status"] if funding_eval["status"] == "NORMAL" else "PAUSED_FUNDING_GUARD",
                    "bounds": {"p_lower": p_lower, "p_upper": p_upper, "grid_count": grid_n}
                },
                "circuit_breaker_3level": cb_eval,
                "multi_timeframe_monitoring": active_monitor_telemetry
            },
            "active_positions": list(self.paper_engine.active_positions.values()),
            "trade_history": self.paper_engine.trade_history[:10]
        }

    def get_scan_interval_sec(self) -> int:
        return 900
