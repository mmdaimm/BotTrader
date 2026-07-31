r"""
WebTraderBot Multi-Timeframe Active Monitoring Engine (Enterprise Specification)
Implements Multi-Timeframe State Machine Architecture:
- Real-Time (1s / WS): Execution, Peak Equity Tracking & Tier 3 Circuit Breaker (-15% Max DD)
- 15m / 30m: Satellite Safety Guard (ADX 4H < 28 & ATR 15m Volatility Spike Guard)
- 4 Hours: Core TWAP Rebalance, Yield Sweep Engine (S >= 2% Total Equity), Geometric Re-gridding
- 1 Day: Macro Trend Guard (BTC < EMA 200 1D -> 30/20/50), Funding Rate Guard (|FR| > 0.1%)
"""

import time
import json
import logging
from typing import Dict, List, Any
from src.core.indicators import TechnicalIndicators
from src.core.database import DatabaseManager

logger = logging.getLogger("ActiveMonitor")

class ActiveMonitor:
    def __init__(self, okx_client, paper_engine, db_manager: DatabaseManager = None, notifier = None):
        self.client = okx_client
        self.paper_engine = paper_engine
        self.db = db_manager or DatabaseManager()
        self.notifier = notifier
        
        # Debounced Timestamps & Recommendation State Tracking
        self.last_1s_ts = 0
        self.last_15m_ts = 0
        self.last_4h_ts = 0
        self.last_1d_ts = 0
        self.scan_interval_sec = 900  # 15 Minutes default Loop
        
        self.last_sent_recommendations = {}  # { "ETH-USDT-SWAP": "Hold" }
        self.last_sent_timestamps = {}       # { "ETH-USDT-SWAP": timestamp }
        
        self.candle_cache = {}          # { "symbol_res": (timestamp, candles) }
        self.last_scan_results = {
            "status": "ACTIVE_MULTI_TIMEFRAME",
            "last_scan_time": "Never",
            "multi_timeframe_state": {
                "realtime_1s_status": "OK",
                "safety_15m_guard": "RUNNING",
                "rebalance_4h_status": "READY",
                "macro_1d_status": "NORMAL_BULL"
            },
            "positions_scanned": 0,
            "warnings_emitted": 0,
            "emergency_closes": 0,
            "details": []
        }

    def _get_cached_candles(self, symbol: str, resolution: str, limit: int = 50) -> List[Dict[str, Any]]:
        cache_key = f"{symbol}_{resolution}"
        now = time.time()
        if cache_key in self.candle_cache:
            ts, candles = self.candle_cache[cache_key]
            if now - ts < 300: # 5 minutes cache
                return candles
                
        try:
            candles = self.client.get_candles(symbol=symbol, resolution=resolution, limit=limit)
            if candles:
                self.candle_cache[cache_key] = (now, candles)
                return candles
        except Exception as e:
            logger.error(f"[ActiveMonitor] Error fetching {resolution} candles for {symbol}: {e}")
        return []

    def send_position_monitoring_telemetry(self, active_positions: list, pair_results: dict):
        """
        Send Telegram Monitoring Status Update for each active position matching user's custom template:
        - If recommendation is "Hold", send once every 1 hour (3600 seconds / 60 scans).
        - If recommendation changes from "Hold" to anything else (Take Profit / Warning SL), send IMMEDIATELY!
        """
        if not self.notifier or not active_positions:
            return

        now = time.time()

        for pos in active_positions:
            sym = pos.get("symbol", "N/A")
            side = pos.get("side", "LONG")
            leverage = pos.get("leverage", 3)
            entry_p = pos.get("entry_price", 0.0)
            
            # Fetch current price & market snapshot from pair_results
            market_snapshot = pair_results.get(sym, {}).get("eval", {}).get("market_snapshot", {})
            curr_price = pair_results.get(sym, {}).get("last_price", entry_p)
            st_direction = market_snapshot.get("st_direction", "GREEN")
            trend_str = "ขาขึ้น (Bullish)" if st_direction == "GREEN" else "ขาลง (Bearish)"

            # Calculate Unrealized PnL
            qty = pos.get("qty", 0.0)
            margin = pos.get("margin_required", 100.0)
            if side == "LONG":
                unrealized_pnl = (curr_price - entry_p) * qty
            else:
                unrealized_pnl = (entry_p - curr_price) * qty
            
            pnl_pct = (unrealized_pnl / margin * 100.0) if margin > 0 else 0.0
            pnl_str = f"+${unrealized_pnl:,.2f} USD (+{pnl_pct:.2f}%)" if unrealized_pnl >= 0 else f"-${abs(unrealized_pnl):,.2f} USD ({pnl_pct:.2f}%)"

            # Recommendation logic (Hold / Take Profit / Warning / Cut)
            if pnl_pct >= 10.0:
                recommendation = "Take Profit (พิจารณาปิดทำกำไรบางส่วน)"
            elif pnl_pct <= -10.0:
                recommendation = "Warning SL (เฝ้าระวังจุดตัดขาดทุน)"
            else:
                recommendation = "Hold"

            # Notification Debouncing & State-Change Logic
            prev_rec = self.last_sent_recommendations.get(sym)
            last_ts = self.last_sent_timestamps.get(sym, 0)
            time_elapsed_sec = now - last_ts

            rec_changed = (prev_rec is not None and prev_rec != recommendation)
            is_hourly_due = (time_elapsed_sec >= 3600)  # 3600 seconds = 1 Hour (60 scans)

            # Send Telegram ONLY if recommendation changed OR 1 hour has passed since last notification
            if rec_changed or prev_rec is None or is_hourly_due:
                msg = (
                    f"<b>📡 [ACTIVE MONITOR REPORT]</b>\n"
                    f"<b>{sym}</b>\n"
                    f"<b>ฝั่ง:</b> {side} ({leverage}x Leverage)\n"
                    f"<b>ราคาเข้า (Entry Price):</b> ${entry_p:,.4f} USD\n"
                    f"<b>ราคาปัจจุบัน (Current Price):</b> ${curr_price:,.4f} USD\n"
                    f"<b>กำไร/ขาดทุนเรียลไทม์ (Unrealized PnL):</b> {pnl_str}\n"
                    f"<b>เทรนด์:</b> {trend_str}\n"
                    f"<b>คำแนะนำ:</b> <b>{recommendation}</b>"
                )
                try:
                    self.notifier.send_message(msg)
                    self.last_sent_recommendations[sym] = recommendation
                    self.last_sent_timestamps[sym] = now
                except Exception as e:
                    logger.error(f"[ActiveMonitor] Telegram send error: {e}")

    def evaluate_multi_timeframe_matrix(self, btc_price: float, total_equity: float, peak_equity: float, adx_4h: float, atr_15m: float, avg_atr_15m: float, btc_ema200_1d: float, funding_rate: float) -> dict:
        r"""
        Multi-Timeframe State Machine Evaluation (Section 4):
        1s: Peak Equity Tracking & Tier 3 Circuit Breaker (-15% Max DD)
        15m: Satellite Safety Guard (ADX 4H >= 28 or ATR Spike > 3x -> Pause Grid)
        4H: Core Rebalance & Yield Sweep ($S >= 2\%$ Total Equity)
        1D: Macro Trend Guard (BTC < EMA 200 1D -> Shift 30/20/50), Funding Rate Guard (|FR| > 0.1%)
        """
        now = time.time()
        
        # 1. Real-Time (1s) Tier 3 Hard Stop Check
        drawdown_pct = max(0.0, (peak_equity - total_equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0
        tier3_hard_stop = (drawdown_pct >= 15.0)

        # 2. 15m / 30m Satellite Safety Guard Check
        volatility_spike = (avg_atr_15m > 0 and atr_15m > 3.0 * avg_atr_15m)
        grid_enabled = (adx_4h < 28.0) and not volatility_spike

        # 3. 4H Core Target & Yield Sweep Check
        core_regime = "BEARISH_GUARD (USDT 50%)" if btc_price < btc_ema200_1d else "NORMAL_BULL (USDT 30%)"

        # 4. 1D Macro & Funding Rate Guard Check
        funding_guard_triggered = abs(funding_rate) > 0.001  # |FR| > 0.1%
        if funding_guard_triggered:
            grid_enabled = False

        state_summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            "realtime_1s": {
                "equity_usd": round(total_equity, 2),
                "peak_equity_usd": round(peak_equity, 2),
                "drawdown_pct": round(drawdown_pct, 2),
                "tier3_hard_stop": tier3_hard_stop
            },
            "safety_15m": {
                "adx_4h": round(adx_4h, 2),
                "atr_15m": round(atr_15m, 4),
                "volatility_spike": volatility_spike,
                "grid_enabled": grid_enabled
            },
            "rebalance_4h": {
                "core_regime": core_regime,
                "target_weights": {"BTC": 0.30, "ETH": 0.20, "USDT": 0.50} if btc_price < btc_ema200_1d else {"BTC": 0.40, "ETH": 0.30, "USDT": 0.30}
            },
            "macro_1d": {
                "btc_price": btc_price,
                "btc_ema200_1d": btc_ema200_1d,
                "funding_rate_pct": round(funding_rate * 100.0, 3),
                "funding_guard_triggered": funding_guard_triggered
            }
        }

        self.last_scan_results = {
            "status": "ACTIVE_MULTI_TIMEFRAME",
            "last_scan_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            "multi_timeframe_state": state_summary,
            "positions_scanned": len(self.paper_engine.active_positions),
            "warnings_emitted": 1 if (volatility_spike or funding_guard_triggered) else 0,
            "emergency_closes": 1 if tier3_hard_stop else 0,
            "details": [state_summary]
        }

        return state_summary
