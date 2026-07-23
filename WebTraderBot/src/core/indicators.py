"""
Technical Indicators Calculation Engine
Pure Python calculation for EMA, RSI, ATR, ADX, VWAP, and Volume SMA.
Includes edge-case bounds checking & zero-division safety.
"""

class TechnicalIndicators:
    @staticmethod
    def calculate_ema(prices: list, period: int) -> list:
        """Calculate Exponential Moving Average (EMA)."""
        if not prices:
            return []
        ema = []
        multiplier = 2 / (period + 1)
        for i, price in enumerate(prices):
            if i == 0:
                ema.append(price)
            else:
                ema.append((price - ema[-1]) * multiplier + ema[-1])
        return ema

    @staticmethod
    def calculate_rsi(prices: list, period: int = 14) -> list:
        """Calculate Relative Strength Index (RSI)."""
        if not prices or len(prices) <= period:
            return [50.0] * (len(prices) if prices else 0)
            
        gains, losses = [], []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
            
        rsi = [50.0] * len(prices)
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0 and avg_gain == 0:
                rsi[i+1] = 50.0
            elif avg_loss == 0:
                rsi[i+1] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i+1] = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    @staticmethod
    def calculate_atr(candles: list, period: int = 14) -> list:
        """Calculate Average True Range (ATR)."""
        if not candles:
            return []
            
        tr = []
        for i in range(len(candles)):
            if i == 0:
                tr.append(candles[i]["high"] - candles[i]["low"])
            else:
                high_low = candles[i]["high"] - candles[i]["low"]
                high_close = abs(candles[i]["high"] - candles[i-1]["close"])
                low_close = abs(candles[i]["low"] - candles[i-1]["close"])
                tr.append(max(high_low, high_close, low_close))
        
        atr = [tr[0]] * len(candles)
        for i in range(1, len(candles)):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
        return atr

    @staticmethod
    def calculate_sma(values: list, period: int = 20) -> list:
        """Calculate Simple Moving Average (SMA)."""
        if not values:
            return []
        sma = []
        for i in range(len(values)):
            if i < period:
                sma.append(sum(values[:i+1]) / (i+1))
            else:
                sma.append(sum(values[i-period+1:i+1]) / period)
        return sma

    @staticmethod
    def calculate_adx(candles: list, period: int = 14) -> list:
        """
        Calculate Average Directional Index (ADX).
        Measures overall trend strength (> 20 indicates strong trend).
        """
        if not candles or len(candles) < period + 1:
            return [20.0] * (len(candles) if candles else 0)
            
        plus_dm = [0.0] * len(candles)
        minus_dm = [0.0] * len(candles)
        tr = [0.0] * len(candles)
        
        for i in range(1, len(candles)):
            up_move = candles[i]["high"] - candles[i-1]["high"]
            down_move = candles[i-1]["low"] - candles[i]["low"]
            
            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move
                
            high_low = candles[i]["high"] - candles[i]["low"]
            high_close = abs(candles[i]["high"] - candles[i-1]["close"])
            low_close = abs(candles[i]["low"] - candles[i-1]["close"])
            tr[i] = max(high_low, high_close, low_close)
            
        atr_smooth = [0.0] * len(candles)
        plus_di_smooth = [0.0] * len(candles)
        minus_di_smooth = [0.0] * len(candles)
        
        if len(candles) > period:
            atr_smooth[period] = sum(tr[1:period+1])
            plus_di_smooth[period] = sum(plus_dm[1:period+1])
            minus_di_smooth[period] = sum(minus_dm[1:period+1])
            
            for i in range(period + 1, len(candles)):
                atr_smooth[i] = atr_smooth[i-1] - (atr_smooth[i-1] / period) + tr[i]
                plus_di_smooth[i] = plus_di_smooth[i-1] - (plus_di_smooth[i-1] / period) + plus_dm[i]
                minus_di_smooth[i] = minus_di_smooth[i-1] - (minus_di_smooth[i-1] / period) + minus_dm[i]
                
        dx = [0.0] * len(candles)
        for i in range(period, len(candles)):
            if atr_smooth[i] > 0:
                plus_di = (plus_di_smooth[i] / atr_smooth[i]) * 100.0
                minus_di = (minus_di_smooth[i] / atr_smooth[i]) * 100.0
                di_diff = abs(plus_di - minus_di)
                di_sum = plus_di + minus_di
                dx[i] = (di_diff / di_sum * 100.0) if di_sum > 0 else 0.0
                
        adx = [20.0] * len(candles)
        if len(candles) >= period * 2:
            adx[period * 2 - 1] = sum(dx[period:period * 2]) / period
            for i in range(period * 2, len(candles)):
                adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period
                
        return adx

    @staticmethod
    def calculate_vwap(candles: list) -> list:
        """Calculate Volume-Weighted Average Price (VWAP)."""
        if not candles:
            return []
        vwap = []
        cum_tp_vol = 0.0
        cum_vol = 0.0
        for c in candles:
            tp = (c["high"] + c["low"] + c["close"]) / 3.0
            vol = c.get("volume", 1.0)
            cum_tp_vol += tp * vol
            cum_vol += vol
            vwap.append(cum_tp_vol / cum_vol if cum_vol > 0 else tp)
        return vwap
