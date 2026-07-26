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

CONTRACT_SIZES = {
    "BTC-USDT-SWAP": 0.01,
    "ETH-USDT-SWAP": 0.1,
    "SOL-USDT-SWAP": 1.0,
    "ADA-USDT-SWAP": 10.0,
    "AVAX-USDT-SWAP": 1.0,
    "XRP-USDT-SWAP": 10.0,
    "DOGE-USDT-SWAP": 100.0,
    "DOT-USDT-SWAP": 1.0,
    "LINK-USDT-SWAP": 1.0,
    "BNB-USDT-SWAP": 0.1,
    "NEAR-USDT-SWAP": 1.0,
    "SUI-USDT-SWAP": 1.0,
    "APT-USDT-SWAP": 1.0,
    "OP-USDT-SWAP": 1.0,
    "ARB-USDT-SWAP": 1.0
}

class OKXClient:
    def __init__(self, api_key: str = None, api_secret: str = None, passphrase: str = None, host: str = "https://www.okx.com", simulated: bool = True):
        self.simulated = simulated
        if simulated:
            self.api_key = (api_key or os.getenv("OKX_DEMO_API_KEY", os.getenv("OKX_API_KEY", ""))).strip()
            self.api_secret = (api_secret or os.getenv("OKX_DEMO_SECRET_KEY", os.getenv("OKX_API_SECRET", ""))).strip()
            self.passphrase = (passphrase or os.getenv("OKX_DEMO_PASSPHRASE", os.getenv("OKX_PASSPHRASE", ""))).strip()
        else:
            self.api_key = (api_key or os.getenv("OKX_LIVE_API_KEY", os.getenv("OKX_API_KEY", ""))).strip()
            self.api_secret = (api_secret or os.getenv("OKX_LIVE_SECRET_KEY", os.getenv("OKX_API_SECRET", ""))).strip()
            self.passphrase = (passphrase or os.getenv("OKX_LIVE_PASSPHRASE", os.getenv("OKX_PASSPHRASE", ""))).strip()
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
            'User-Agent': 'Mozilla/5.0',
            'x-simulated-trading': '1' if self.simulated else '0'
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

    def get_orderbook(self, symbol: str = "BTC-USDT-SWAP", depth: int = 10) -> dict:
        """Fetch real-time OKX Orderbook Depth (Bids / Asks)."""
        try:
            url = f"{self.host}/api/v5/market/books?instId={symbol}&sz={depth}"
            req = urllib.request.Request(url, headers=self._get_headers("GET", f"/api/v5/market/books?instId={symbol}&sz={depth}"))
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                if data.get("code") == "0" and data.get("data"):
                    book = data["data"][0]
                    return {
                        "status": "SUCCESS",
                        "symbol": symbol,
                        "bids": [[float(b[0]), float(b[1])] for b in book.get("bids", [])],
                        "asks": [[float(a[0]), float(a[1])] for a in book.get("asks", [])],
                        "timestamp": int(book.get("ts", time.time() * 1000))
                    }
        except Exception as e:
            print(f"[OKXClient] Orderbook fetch exception: {e}")
        return {"status": "ERROR", "bids": [], "asks": [], "symbol": symbol}

    def get_account_balance(self) -> dict:
        """Fetch OKX Demo / Live Account Balance & Margin Health."""
        if not self.api_key or not self.api_secret or not self.passphrase:
            return {
                "status": "UNCONFIGURED_KEY",
                "simulated": self.simulated,
                "message": "OKX Demo API Key is missing in Railway Variables",
                "total_equity": None,
                "available_margin": None,
                "margin_ratio": 0.0
            }

        try:
            path = "/api/v5/account/balance"
            url = f"{self.host}{path}"
            headers = self._get_headers("GET", path)
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                if data.get("code") == "0" and data.get("data"):
                    bal = data["data"][0]
                    total_eq = float(bal.get("totalEq", 0.0))
                    iso_eq = float(bal.get("isoEq", 0.0))
                    adj_eq = float(bal.get("adjEq", total_eq))
                    ord_froz = float(bal.get("ordFroz", 0.0))
                    mgn_ratio = float(bal.get("mgnRatio", 0.0))
                    
                    details = bal.get("details", [])
                    usdt_avail = total_eq
                    for d in details:
                        if d.get("ccy") == "USDT":
                            usdt_avail = float(d.get("availBal", total_eq))

                    return {
                        "status": "SUCCESS",
                        "simulated": self.simulated,
                        "total_equity": total_eq,
                        "available_margin": usdt_avail,
                        "margin_ratio": mgn_ratio,
                        "iso_equity": iso_eq,
                        "frozen_order_val": ord_froz,
                        "currency_details": details
                    }
                else:
                    return {
                        "status": "API_ERROR",
                        "simulated": self.simulated,
                        "code": data.get("code"),
                        "message": data.get("msg", "OKX API error"),
                        "total_equity": None
                    }
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode('utf-8')
                err_json = json.loads(err_body)
                msg = f"OKX HTTP {e.code} ({err_json.get('code')}): {err_json.get('msg', e.reason)}"
            except Exception:
                msg = f"HTTP {e.code}: {e.reason}"
            print(f"[OKXClient] HTTPError fetching balance: {msg}")
            return {
                "status": "HTTP_ERROR",
                "simulated": self.simulated,
                "message": msg,
                "total_equity": None
            }
        except Exception as e:
            print(f"[OKXClient] Balance fetch exception: {e}")
            return {
                "status": "FETCH_ERROR",
                "simulated": self.simulated,
                "message": str(e),
                "total_equity": None
            }
