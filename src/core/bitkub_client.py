"""
Bitkub & Multi-Crypto Exchange API Client Engine
Handles Public Market Data & Dynamic Multi-Crypto Pair Support (BTC, ETH, SOL, XRP, DOGE, etc.).
"""

import hmac
import hashlib
import json
import time
import urllib.request
import urllib.parse
import os

# Mapping Bitkub THB pairs to Binance USDT pairs for global high-liquidity candlestick feeds
SYMBOL_MAP = {
    "THB_BTC": "BTCUSDT",
    "THB_ETH": "ETHUSDT",
    "THB_SOL": "SOLUSDT",
    "THB_XRP": "XRPUSDT",
    "THB_DOGE": "DOGEUSDT",
    "THB_ADA": "ADAUSDT",
    "THB_BNB": "BNBUSDT"
}

class BitkubClient:
    def __init__(self, api_key: str = None, api_secret: str = None, host: str = "https://api.bitkub.com"):
        self.api_key = api_key or os.getenv("BITKUB_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BITKUB_API_SECRET", "")
        self.host = host

    def _get_headers(self, sign: str = None) -> dict:
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        }
        if self.api_key:
            headers['X-BTK-TIMESTAMP'] = str(int(time.time() * 1000))
            headers['X-BTK-APIKEY'] = self.api_key
        if sign:
            headers['X-BTK-SIGN'] = sign
        return headers

    def _generate_signature(self, timestamp: int, method: str, path: str, body: str = "") -> str:
        payload = f"{timestamp}{method}{path}{body}"
        return hmac.new(
            self.api_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def get_server_time(self) -> int:
        """Fetch server timestamp in milliseconds."""
        url = f"{self.host}/api/v3/servertime"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            return data.get("result", int(time.time() * 1000))

    def get_ticker(self, symbol: str = "THB_BTC") -> dict:
        """Fetch real-time ticker for any crypto pair."""
        try:
            url = f"{self.host}/api/market/ticker?sym={symbol}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                return data.get(symbol, {})
        except Exception:
            return {}

    def get_candles(self, symbol: str = "THB_BTC", resolution: str = "15", limit: int = 300) -> list:
        """
        Fetch OHLCV candlestick historical data for any crypto pair.
        Supports multi-crypto assets (BTC, ETH, SOL, XRP, DOGE, etc.).
        """
        binance_symbol = SYMBOL_MAP.get(symbol, symbol if "USDT" in symbol else f"{symbol.replace('THB_', '')}USDT")
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval={resolution}m&limit={limit}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                candles = []
                for item in data:
                    candles.append({
                        "timestamp": int(item[0]) // 1000,
                        "open": float(item[1]),
                        "high": float(item[2]),
                        "low": float(item[3]),
                        "close": float(item[4]),
                        "volume": float(item[5])
                    })
                return candles
        except Exception as e:
            print(f"[BitkubClient] Error fetching candles for {symbol} ({binance_symbol}): {e}")
            return []
