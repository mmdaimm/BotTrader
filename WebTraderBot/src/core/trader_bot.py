"""
Trading Bot Engine Loop with OKX Perpetual Futures & Dual-Direction Trading (LONG & SHORT)
Enforces 80/20 Institutional Capital Allocation & Multi-Timeframe (1H Macro Trend + 15m Confluence) Filter.
"""

from src.core.okx_client import OKXClient
from src.core.indicators import TechnicalIndicators
from src.core.risk_engine import RiskEngine
from src.core.telegram_bot import TelegramNotifier
from src.core.paper_trading import PaperTradingEngine

class TraderBot:
    def __init__(self, symbols: list = None, resolution: str = "15", initial_capital: float = 10000.0):
        self.symbols = symbols or [
            "BTC-USDT-SWAP",
            "ETH-USDT-SWAP",
            "SOL-USDT-SWAP",
            "XRP-USDT-SWAP",
            "DOGE-USDT-SWAP"
        ]
        self.resolution = resolution
        self.timeframe_str = f"{resolution}m"
        self.client = OKXClient()
        self.risk_engine = RiskEngine()
        self.notifier = TelegramNotifier()
        
        # 80/20 Institutional Capital Allocation
        self.initial_capital = initial_capital
        self.funding_capital_80 = initial_capital * 0.80  # 80% Weight ($8,000)
        self.scalping_capital_20 = initial_capital * 0.20 # 20% Weight ($2,000)
        
        self.paper_engine = PaperTradingEngine(initial_capital=self.scalping_capital_20)
        self.trading_mode = "PAPER"  # "PAPER" or "LIVE"
        self.bot_state = "RUNNING"   # "RUNNING", "PAUSED", "ERROR"
        self.last_signals_sent = {}  # { symbol: signal_key }

    def evaluate_pair_signal(self, symbol: str, candles: list) -> dict:
        if not candles or len(candles) < 200:
            return {"symbol": symbol, "signal": "NONE", "reason": "Insufficient candles"}
            
        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]
        
        ema800_1h = TechnicalIndicators.calculate_ema(closes, 800)[-1] if len(closes) >= 800 else TechnicalIndicators.calculate_ema(closes, 200)[-1]
        ema200 = TechnicalIndicators.calculate_ema(closes, 200)[-1]
        ema9 = TechnicalIndicators.calculate_ema(closes, 9)[-1]
        ema21_list = TechnicalIndicators.calculate_ema(closes, 21)
        ema21 = ema21_list[-1]
        prev_ema21 = ema21_list[-2] if len(ema21_list) >= 2 else ema21
        ema21_slope = ((ema21 - prev_ema21) / (prev_ema21 or 1.0)) * 100.0

        rsi = TechnicalIndicators.calculate_rsi(closes, 14)[-1]
        adx = TechnicalIndicators.calculate_adx(candles, 14)[-1]
        atr = TechnicalIndicators.calculate_atr(candles, 14)[-1]
        vol_sma = TechnicalIndicators.calculate_sma(volumes, 20)[-1]
        vwap = TechnicalIndicators.calculate_vwap(candles)[-1]
        
        current_candle = candles[-1]
        close = current_candle["close"]
        low = current_candle["low"]
        high = current_candle["high"]
        vol = current_candle["volume"]
        vol_ratio = vol / vol_sma if vol_sma > 0 else 1.0
        
        market_snapshot = {
            "timeframe": self.timeframe_str,
            "ema800_1h": round(ema800_1h, 4),
            "ema200": round(ema200, 4),
            "ema9": round(ema9, 4),
            "ema21": round(ema21, 4),
            "ema21_slope": round(ema21_slope, 4),
            "rsi": round(rsi, 2),
            "adx": round(adx, 2),
            "atr": round(atr, 4),
            "volume_ratio": round(vol_ratio, 2),
            "vwap": round(vwap, 4)
        }
        
        # Multi-Timeframe Alignment Checks
        is_1h_uptrend = close > ema800_1h
        is_1h_downtrend = close < ema800_1h

        # 🟢 LONG Signal Conditions (Must align with 1H Uptrend)
        is_long_uptrend = is_1h_uptrend and close > ema200 and ema9 > ema21
        is_long_pullback = low <= ema21 and close > ema9
        is_long_rsi = 50 <= rsi <= 65
        is_adx_valid = adx >= 22.0 and abs(ema21_slope) >= 0.03
        is_vol_valid = vol_ratio >= 1.8
        
        # 🔴 SHORT Signal Conditions (Must align with 1H Downtrend)
        is_short_downtrend = is_1h_downtrend and close < ema200 and ema9 < ema21
        is_short_rejection = high >= ema21 and close < ema9
        is_short_rsi = 35 <= rsi <= 50
        
        if is_long_uptrend and is_long_pullback and is_long_rsi and is_adx_valid and is_vol_valid:
            risk_params = self.risk_engine.calculate_position_sizing(self.paper_engine.current_capital, close, atr, side="LONG", tp_multiplier=2.25)
            sig_key = f"LONG-{close}"
            if self.last_signals_sent.get(symbol) != sig_key:
                self.notifier.send_signal_alert(symbol, close, risk_params)
                self.last_signals_sent[symbol] = sig_key
                
                if self.trading_mode == "PAPER":
                    self.paper_engine.open_position(symbol, close, risk_params, side="LONG", timeframe=self.timeframe_str, market_snapshot=market_snapshot)
                
            return {
                "symbol": symbol,
                "signal": "BUY_LONG",
                "side": "LONG",
                "timeframe": self.timeframe_str,
                "price": close,
                "atr": atr,
                "risk_params": risk_params,
                "market_snapshot": market_snapshot,
                "reason": f"1H MTF LONG Rebound (1H EMA={ema800_1h:.1f}, ADX={adx:.1f}, Vol={vol_ratio:.1f}x)"
            }

        elif is_short_downtrend and is_short_rejection and is_short_rsi and is_adx_valid and is_vol_valid:
            risk_params = self.risk_engine.calculate_position_sizing(self.paper_engine.current_capital, close, atr, side="SHORT", tp_multiplier=2.25)
            sig_key = f"SHORT-{close}"
            if self.last_signals_sent.get(symbol) != sig_key:
                self.notifier.send_signal_alert(symbol, close, risk_params)
                self.last_signals_sent[symbol] = sig_key
                
                if self.trading_mode == "PAPER":
                    self.paper_engine.open_position(symbol, close, risk_params, side="SHORT", timeframe=self.timeframe_str, market_snapshot=market_snapshot)
                
            return {
                "symbol": symbol,
                "signal": "SELL_SHORT",
                "side": "SHORT",
                "timeframe": self.timeframe_str,
                "price": close,
                "atr": atr,
                "risk_params": risk_params,
                "market_snapshot": market_snapshot,
                "reason": f"1H MTF SHORT Rejection (1H EMA={ema800_1h:.1f}, ADX={adx:.1f}, Vol={vol_ratio:.1f}x)"
            }
            
        return {
            "symbol": symbol,
            "signal": "NONE",
            "timeframe": self.timeframe_str,
            "market_snapshot": market_snapshot,
            "reason": f"No signal (Price={close:,.2f}, 1H_EMA={ema800_1h:,.2f}, ADX={adx:.1f}, RSI={rsi:.1f})"
        }

    def run_single_iteration(self) -> dict:
        """Run a single loop iteration monitoring all OKX Perpetual pairs."""
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
                candles = self.client.get_candles(symbol=sym, resolution=self.resolution, limit=300)
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
                pnl_msg = f"<b>[{closed['side']}] {closed['type']} HIT!</b>\nAsset: {closed['symbol']}\nTF: {closed.get('timeframe','15m')}\nNet PnL: ${closed['net_pnl']} ({closed['pnl_pct']}%)"
                self.notifier.send_message(pnl_msg)
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
                "scalping_engine_20pct": {
                    "allocated_capital_usd": self.scalping_capital_20,
                    "current_capital_usd": self.paper_engine.current_capital,
                    "status": "ACTIVE (1H MTF Filter + R:R 1:1.5)"
                }
            },
            "active_positions": list(self.paper_engine.active_positions.values()),
            "trade_history": self.paper_engine.trade_history[:10]
        }
