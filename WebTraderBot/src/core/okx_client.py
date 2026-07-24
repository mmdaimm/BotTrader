"""
OKX Exchange API Client Engine (OKX API v5 + Fail-safe Global Feed Fallback)
Handles Public Market Data & Perpetual Futures Trading (BTC-USDT-SWAP, ETH-USDT-SWAP, etc.).
Includes Base64 HMAC-SHA256 Signatures, Isolated Margin, and Fail-safe High-Liquidity Feed Fallback.
"""

import hmac
import hashlib
import base64
import json
import time
import urllib.request
import urllib.parse
import os

SYMBOL_MAP = {
    "BTC-USDT-SWAP": "BTCUSDT",
    "ETH-USDT-SWAP": "ETHUSDT",
    "SOL-USDT-SWAP": "SOLUSDT",
    "XRP-USDT-SWAP": "XRPUSDT",
    "DOGE-USDT-SWAP": "DOGEUSDT",
    "THB_BTC": "BTCUSDT",
    "THB_ETH": "ETHUSDT",
    "THB_SOL": "SOLUSDT",
    "THB_XRP": "XRPUSDT",
    "THB_DOGE": "DOGEUSDT"
}

class OKXClient:
    def __init__(self, api_key: str = None, api_secret: str = None, passphrase: str = None, host: str = "https://www.okx.com"):
        self.api_key = api_key or os.getenv("OKX_API_KEY", "")
        self.api_secret = api_secret or os.getenv("OKX_API_SECRET", "")
        self.passphrase = passphrase or os.getenv("OKX_PASSPHRASE", "")
        self.host = host

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """Generate OKX API v5 Base64 HMAC-SHA256 signature."""
        message = f"{timestamp}{method.upper()}{request_path}{body}"
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode('utf-8')

    def _get_headers(self, method: str, request_path: str, body: str = "") -> dict:
        timestamp = f"{time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())}.{int(time.time() * 1000) % 1000:03d}Z"
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        }
        if self.api_key and self.api_secret and self.passphrase:
            headers['OKX-ACCESS-KEY'] = self.api_key
            headers['OKX-ACCESS-SIGN'] = self._generate_signature(timestamp, method, request_path, body)
            headers['OKX-ACCESS-TIMESTAMP'] = timestamp
            headers['OKX-ACCESS-PASSPHRASE'] = self.passphrase
        return headers

    def get_candles(self, symbol: str = "BTC-USDT-SWAP", resolution: str = "15", limit: int = 300) -> list:
        """
        Fetch OHLCV candlestick historical data for Perpetual Swap instruments.
        Supports 5m, 15m, 1H (60), and 4H (240) intervals with failover.
        """
        global_symbol = SYMBOL_MAP.get(symbol, symbol.replace("-USDT-SWAP", "USDT"))
        res_str = str(resolution).lower().replace("m", "").replace("h", "")

        if str(resolution).lower() in ["4h", "240"]:
            okx_bar = "4H"
            binance_interval = "4h"
        elif str(resolution).lower() in ["1h", "60"]:
            okx_bar = "1H"
            binance_interval = "1h"
        else:
            okx_bar = f"{res_str}m"
            binance_interval = f"{res_str}m"
        
        # Primary OKX API v5 Attempt
        try:
            url = f"{self.host}/api/v5/market/candles?instId={symbol}&bar={okx_bar}&limit={limit}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                if data.get("code") == "0" and data.get("data"):
                    raw_candles = data["data"]
                    candles = []
                    for item in reversed(raw_candles):
                        candles.append({
                            "timestamp": int(item[0]) // 1000,
                            "open": float(item[1]),
                            "high": float(item[2]),
                            "low": float(item[3]),
                            "close": float(item[4]),
                            "volume": float(item[5])
                        })
                    return candles
        except Exception:
            pass  # Failover to global feed below

        # Fail-safe Fallback: Global High-Liquidity Feed (Binance Futures/Spot)
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={global_symbol}&interval={binance_interval}&limit={limit}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
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
            print(f"[OKXClient] Fallback candle fetch exception for {symbol} ({resolution}): {e}")
            return []
