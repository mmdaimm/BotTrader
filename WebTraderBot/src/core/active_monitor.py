"""
WebTraderBot Active Monitoring & Dynamic Trade Management Engine
Provides 30-minute Multi-Timeframe Matrix (4H / 1H / 15m) active scanning for open positions.
Features 4 Anti-Noise Filtering Layers (Grace Period, 4H ATR Barrier, 1H Structure, 15m Confluence)
and JSON Indicator Snapshot Audit Logging.
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
        self.last_scan_timestamp = 0
        self.scan_interval_sec = 1800  # 30 Minutes Loop
        self.candle_cache = {}          # { "symbol_res": (timestamp, candles) }
        self.last_scan_results = {
            "status": "IDLE",
            "last_scan_time": "Never",
            "positions_scanned": 0,
            "warnings_emitted": 0,
            "emergency_closes": 0,
            "details": []
        }

    def _get_cached_candles(self, symbol: str, resolution: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch candles with 5-minute caching guard to avoid OKX API rate limits (HTTP 429)."""
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

    def evaluate_position(self, pos: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate an active position against the Multi-Timeframe Matrix (4H / 1H / 15m).
        Returns decision dict with level: IGNORE, LEVEL1_WARNING, LEVEL2_EMERGENCY_CLOSE.
        """
        symbol = pos["symbol"]
        side = pos["side"]
        entry_price = pos["entry_price"]
        entry_ts = pos.get("entry_timestamp", time.time())
        now = time.time()
        pos_age_sec = now - entry_ts

        # Layer 1: Time-Based Grace Period Lockout Check (8 Hours = 28,800 seconds)
        in_grace_period = pos_age_sec < 28800

        # Fetch candles across timeframes
        candles_4h = self._get_cached_candles(symbol, "4H", 30)
        candles_1h = self._get_cached_candles(symbol, "1H", 30)
        candles_15m = self._get_cached_candles(symbol, "15m", 30)

        if not candles_4h or not candles_1h or not candles_15m:
            return {"level": "IGNORE", "reason": "Insufficient candle data"}

        current_price = candles_15m[-1]["close"]

        # 4H Macro Indicators
        atr_4h_list = TechnicalIndicators.calculate_atr(candles_4h, 14)
        atr_4h = atr_4h_list[-1] if atr_4h_list else (entry_price * 0.03)

        # Layer 2: 4H Macro ATR Adverse Distance Check
        adverse_distance = abs(current_price - entry_price)
        is_adverse_move = (side == "LONG" and current_price < entry_price) or (side == "SHORT" and current_price > entry_price)
        is_beyond_atr_barrier = is_adverse_move and (adverse_distance > (1.0 * atr_4h))

        # 1H Structure Indicators (ChoCh & EMA 9/21 Cross)
        closes_1h = [c["close"] for c in candles_1h]
        highs_1h = [c["high"] for c in candles_1h]
        lows_1h = [c["low"] for c in candles_1h]
        ema9_1h = TechnicalIndicators.calculate_ema(closes_1h, 9)
        ema21_1h = TechnicalIndicators.calculate_ema(closes_1h, 21)

        # 1H ChoCh (Change of Character)
        swing_high_1h = max(highs_1h[-7:-1])
        swing_low_1h = min(lows_1h[-7:-1])
        is_1h_choch = (side == "SHORT" and current_price > swing_high_1h) or (side == "LONG" and current_price < swing_low_1h)

        # 1H EMA 9/21 Cross
        is_1h_ema_cross = (side == "SHORT" and ema9_1h[-1] > ema21_1h[-1]) or (side == "LONG" and ema9_1h[-1] < ema21_1h[-1])
        is_1h_reversal = is_1h_choch or is_1h_ema_cross

        # 15m Momentum & Institutional Volume Indicators
        closes_15m = [c["close"] for c in candles_15m]
        highs_15m = [c["high"] for c in candles_15m]
        lows_15m = [c["low"] for c in candles_15m]
        vols_15m = [c["volume"] for c in candles_15m]

        vma20_15m = TechnicalIndicators.calculate_sma(vols_15m, 20)[-1]
        vol_current_15m = vols_15m[-1]
        is_vol_spike = vol_current_15m > (2.5 * vma20_15m)

        adx_15m_list = TechnicalIndicators.calculate_adx(candles_15m, 14)
        adx_15m = adx_15m_list[-1] if adx_15m_list else 20.0
        is_strong_trend = adx_15m > 25.0

        rsi_15m = TechnicalIndicators.calculate_rsi(closes_15m, 14)[-1]
        ema20_15m = TechnicalIndicators.calculate_ema(closes_15m, 20)[-1]

        # Snapshot for Audit Log
        indicator_snapshot = {
            "symbol": symbol,
            "side": side,
            "current_price": current_price,
            "entry_price": entry_price,
            "adverse_distance": round(adverse_distance, 4),
            "atr_4h": round(atr_4h, 4),
            "pos_age_hours": round(pos_age_sec / 3600, 2),
            "in_grace_period": in_grace_period,
            "1h_choch": is_1h_choch,
            "1h_ema_cross": is_1h_ema_cross,
            "vol_ratio_15m": round(vol_current_15m / vma20_15m, 2) if vma20_15m > 0 else 1.0,
            "adx_15m": round(adx_15m, 2),
            "rsi_15m": round(rsi_15m, 2)
        }

        # Decision Evaluation:
        # Level 2 Emergency Auto-Close
        if not in_grace_period and is_beyond_atr_barrier and is_1h_reversal and is_vol_spike and is_strong_trend:
            return {
                "level": "LEVEL2_EMERGENCY_CLOSE",
                "reason": "Emergency Reversal: 1H Structure Broken + 15m Vol Spike (>2.5x) & ADX (>25)",
                "snapshot": indicator_snapshot
            }

        # Level 1 Warning Alert
        is_l1_warning = (side == "SHORT" and current_price > ema20_15m and rsi_15m > 60.0) or \
                        (side == "LONG" and current_price < ema20_15m and rsi_15m < 40.0)
        if is_l1_warning:
            return {
                "level": "LEVEL1_WARNING",
                "reason": f"15m Momentum Shift against {side} (RSI: {rsi_15m:.1f}, Price vs EMA20)",
                "snapshot": indicator_snapshot
            }

        return {"level": "IGNORE", "reason": "Retracement within normal parameters", "snapshot": indicator_snapshot}

    def run_30m_scan(self) -> Dict[str, Any]:
        """Execute 30-minute Active Monitoring scan across all open positions."""
        now = time.time()
        self.last_scan_timestamp = now
        active_positions = list(self.paper_engine.active_positions.values())

        details = []
        warnings_count = 0
        closes_count = 0

        for pos in active_positions:
            eval_res = self.evaluate_position(pos)
            level = eval_res.get("level", "IGNORE")
            symbol = pos["symbol"]
            snapshot = eval_res.get("snapshot", {})

            details.append({"symbol": symbol, "level": level, "reason": eval_res.get("reason"), "snapshot": snapshot})

            if level == "LEVEL1_WARNING":
                warnings_count += 1
                msg = f"⚠️ [ACTIVE MONITOR WARNING] {symbol} {pos['side']} showing short-term 15m momentum push. {eval_res['reason']}"
                logger.warning(msg)
                self.db.log_audit_event("LEVEL1_WARNING", json.dumps({"message": msg, "snapshot": snapshot}))
                if self.notifier:
                    self.notifier.send_message(f"<b>{msg}</b>\n<code>{json.dumps(snapshot, indent=2)}</code>")

            elif level == "LEVEL2_EMERGENCY_CLOSE":
                closes_count += 1
                msg = f"🚨 [ACTIVE MONITOR EMERGENCY CLOSE] Executing Market Close on {symbol} {pos['side']}. {eval_res['reason']}"
                logger.error(msg)
                self.db.log_audit_event("EMERGENCY_CLOSE", json.dumps({"message": msg, "snapshot": snapshot}))
                
                # Execute Market Close
                candles_15m = self._get_cached_candles(symbol, "15m", 5)
                current_p = candles_15m[-1]["close"] if candles_15m else pos["entry_price"]
                close_res = self.paper_engine.close_position_manually(symbol, current_p)

                if self.notifier:
                    self.notifier.send_message(
                        f"<b>{msg}</b>\n"
                        f"<b>Exit Price:</b> ${close_res.get('trade_record', {}).get('exit_price', current_p):,.4f}\n"
                        f"<b>PnL:</b> ${close_res.get('trade_record', {}).get('net_pnl', 0.0):,.2f}\n"
                        f"<code>{json.dumps(snapshot, indent=2)}</code>"
                    )

        self.last_scan_results = {
            "status": "ACTIVE",
            "last_scan_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            "positions_scanned": len(active_positions),
            "warnings_emitted": warnings_count,
            "emergency_closes": closes_count,
            "details": details
        }
        return self.last_scan_results
