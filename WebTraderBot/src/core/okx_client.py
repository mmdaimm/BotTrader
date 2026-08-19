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
    "BCH-USDT-SWAP": 0.1,
    "LTC-USDT-SWAP": 1.0,
    "ATOM-USDT-SWAP": 1.0,
    "ETC-USDT-SWAP": 1.0,
    "XLM-USDT-SWAP": 10.0,
    "TRX-USDT-SWAP": 100.0,
    "BNB-USDT-SWAP": 0.1,
    "NEAR-USDT-SWAP": 1.0,
    "UNI-USDT-SWAP": 1.0,
    "FIL-USDT-SWAP": 1.0,
    "ALGO-USDT-SWAP": 10.0
}

class OKXClient:
    def __init__(self, api_key: str = None, api_secret: str = None, passphrase: str = None, host: str = "https://www.okx.com", simulated: bool = True):
        self.simulated = simulated
        if simulated:
            env_key = os.getenv("OKX_DEMO_API_KEY") or os.getenv("OKX_API_KEY") or os.getenv("OKX_KEY") or ""
            env_secret = os.getenv("OKX_DEMO_SECRET_KEY") or os.getenv("OKX_API_SECRET") or os.getenv("OKX_SECRET") or ""
            env_passphrase = os.getenv("OKX_DEMO_PASSPHRASE") or os.getenv("OKX_PASSPHRASE") or ""
            self.api_key = (api_key or env_key).strip()
            self.api_secret = (api_secret or env_secret).strip()
            self.passphrase = (passphrase or env_passphrase).strip()
        else:
            env_key = os.getenv("OKX_LIVE_API_KEY") or os.getenv("OKX_API_KEY") or os.getenv("OKX_KEY") or ""
            env_secret = os.getenv("OKX_LIVE_SECRET_KEY") or os.getenv("OKX_API_SECRET") or os.getenv("OKX_SECRET") or ""
            env_passphrase = os.getenv("OKX_LIVE_PASSPHRASE") or os.getenv("OKX_PASSPHRASE") or ""
            self.api_key = (api_key or env_key).strip()
            self.api_secret = (api_secret or env_secret).strip()
            self.passphrase = (passphrase or env_passphrase).strip()
        self.host = host

    def _resolve_keys(self):
        """Dynamically resolve environment keys at runtime if empty on boot."""
        def _get_non_empty(var_names):
            for name in var_names:
                val = os.getenv(name)
                if val is not None and len(str(val).strip()) > 0:
                    return str(val).strip()
            return ""

        if not self.api_key or not self.api_secret or not self.passphrase:
            okx_envs = {k: f"len={len(v)}" for k, v in os.environ.items() if "OKX" in k.upper() or "DEMO" in k.upper() or "ACCESS" in k.upper()}
            print(f"[OKXClient] Runtime key audit - envs_found: {okx_envs}")

        if self.simulated:
            if not self.api_key:
                self.api_key = _get_non_empty(["OKX_DEMO_API_KEY", "OKX_ACCESS_KEY", "OKX_API_KEY", "OKX_KEY"])
            if not self.api_secret:
                self.api_secret = _get_non_empty(["OKX_DEMO_SECRET_KEY", "OKX_ACCESS_SECRET", "OKX_SECRET_KEY", "OKX_API_SECRET", "OKX_SECRET"])
            if not self.passphrase:
                self.passphrase = _get_non_empty(["OKX_DEMO_PASSPHRASE", "OKX_ACCESS_PASSPHRASE", "OKX_PASSPHRASE"])
        else:
            if not self.api_key:
                self.api_key = _get_non_empty(["OKX_LIVE_API_KEY", "OKX_ACCESS_KEY", "OKX_API_KEY", "OKX_KEY"])
            if not self.api_secret:
                self.api_secret = _get_non_empty(["OKX_LIVE_SECRET_KEY", "OKX_ACCESS_SECRET", "OKX_SECRET_KEY", "OKX_API_SECRET", "OKX_SECRET"])
            if not self.passphrase:
                self.passphrase = _get_non_empty(["OKX_LIVE_PASSPHRASE", "OKX_ACCESS_PASSPHRASE", "OKX_PASSPHRASE"])

        if self.api_key and self.api_secret and self.passphrase:
            print(f"[OKXClient] Key resolved! API Key len: {len(self.api_key)}, Secret len: {len(self.api_secret)}, Passphrase len: {len(self.passphrase)}")
        else:
            print(f"[OKXClient] WARNING: OKX API Key is STILL MISSING! (Key len={len(self.api_key)}, Secret len={len(self.api_secret)}, Passphrase len={len(self.passphrase)})")

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """Generate OKX API v5 Base64 HMAC-SHA256 signature."""
        self._resolve_keys()
        message = f"{timestamp}{method.upper()}{request_path}{body}"
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode('utf-8')

    def _get_headers(self, method: str, request_path: str, body: str = "") -> dict:
        self._resolve_keys()
        timestamp = f"{time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())}.{int(time.time() * 1000) % 1000:03d}Z"
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0',
            'x-simulated-trading': '1' if self.simulated else '0'
        }
        if self.api_key and self.api_secret and self.passphrase:
            sig = self._generate_signature(timestamp, method, request_path, body)
            # Standard OKX V5 API Header Keys
            headers['OK-ACCESS-KEY'] = self.api_key
            headers['OK-ACCESS-SIGN'] = sig
            headers['OK-ACCESS-TIMESTAMP'] = timestamp
            headers['OK-ACCESS-PASSPHRASE'] = self.passphrase
            # Fallback OKX- Variant Header Keys
            headers['OKX-ACCESS-KEY'] = self.api_key
            headers['OKX-ACCESS-SIGN'] = sig
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

    def get_funding_rate(self, symbol: str = "BTC-USDT-SWAP") -> dict:
        """Fetch real-time OKX Funding Rate (GET /api/v5/public/funding-rate)."""
        try:
            url = f"{self.host}/api/v5/public/funding-rate?instId={symbol}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                if data.get("code") == "0" and data.get("data"):
                    item = data["data"][0]
                    fr = float(item.get("fundingRate", 0.0001))
                    next_fr = float(item.get("nextFundingRate", fr))
                    annual_apy = fr * 3 * 365 * 100.0
                    return {
                        "status": "SUCCESS",
                        "symbol": symbol,
                        "funding_rate": fr,
                        "next_funding_rate": next_fr,
                        "annual_apy_pct": round(annual_apy, 2),
                        "funding_time": item.get("fundingTime")
                    }
        except Exception as e:
            print(f"[OKXClient] Funding rate fetch exception for {symbol}: {e}")
        return {"status": "ERROR", "symbol": symbol, "funding_rate": 0.0001, "annual_apy_pct": 10.95}

    def get_account_balance(self) -> dict:
        """Fetch OKX Demo / Live Account Balance & Margin Health."""
        self._resolve_keys()
        if not self.api_key or not self.api_secret or not self.passphrase:
            msg = f"OKX Demo API Key missing in Railway Variables (Key len={len(self.api_key)}, Secret len={len(self.api_secret)}, Passphrase len={len(self.passphrase)})"
            print(f"[OKXClient] {msg}")
            return {
                "status": "UNCONFIGURED_KEY",
                "simulated": self.simulated,
                "message": msg,
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
                    
                    def safe_float(val, default=0.0):
                        try:
                            if val is None or str(val).strip() == "":
                                return float(default)
                            return float(val)
                        except (ValueError, TypeError):
                            return float(default)

                    total_eq = safe_float(bal.get("totalEq"), 0.0)
                    iso_eq = safe_float(bal.get("isoEq"), 0.0)
                    adj_eq = safe_float(bal.get("adjEq"), total_eq)
                    ord_froz = safe_float(bal.get("ordFroz"), 0.0)
                    mgn_ratio = safe_float(bal.get("mgnRatio"), 0.0)
                    
                    details = bal.get("details", [])
                    usdt_avail = total_eq
                    for d in details:
                        if d.get("ccy") == "USDT":
                            usdt_avail = safe_float(d.get("availBal") or d.get("eq") or d.get("cashBal"), total_eq)

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

    def place_market_order(self, symbol: str, side: str, sz: float, sl_price: float = None, tp_price: float = None, td_mode: str = "isolated") -> dict:
        """
        Place Market Order on OKX Demo / Live API (POST /api/v5/trade/order).
        Supports automatic SL & TP Attached Algo Orders (attachAlgoOrds).
        side: 'LONG' (buy long) or 'SHORT' (sell short)
        """
        self._resolve_keys()
        if not self.api_key or not self.api_secret or not self.passphrase:
            return {"status": "ERROR", "message": "OKX API Keys missing on server"}

        try:
            path = "/api/v5/trade/order"
            url = f"{self.host}{path}"
            
            side_str = "buy" if side.upper() == "LONG" else "sell"
            pos_side = "long" if side.upper() == "LONG" else "short"
            
            contract_multiplier = CONTRACT_SIZES.get(symbol, 1.0)
            sz_contracts = max(1, int(round(sz / contract_multiplier)))

            # Build clean attached SL/TP algo orders
            algo_item = {}
            if sl_price and float(sl_price) > 0:
                algo_item["slTriggerPx"] = f"{float(sl_price):.4f}"
                algo_item["slOrdPx"] = "-1"
            if tp_price and float(tp_price) > 0:
                algo_item["tpTriggerPx"] = f"{float(tp_price):.4f}"
                algo_item["tpOrdPx"] = "-1"

            def _execute_order(p_dict):
                b_str = json.dumps(p_dict)
                hdrs = self._get_headers("POST", path, b_str)
                req_obj = urllib.request.Request(url, data=b_str.encode('utf-8'), headers=hdrs, method="POST")
                with urllib.request.urlopen(req_obj, timeout=5) as resp:
                    d = json.loads(resp.read().decode())
                    if d.get("code") == "0" and d.get("data"):
                        info = d["data"][0]
                        s_code = str(info.get("sCode", "0"))
                        if s_code == "0":
                            return {
                                "status": "SUCCESS",
                                "order_id": info.get("ordId"),
                                "symbol": symbol,
                                "side": side,
                                "contracts": sz_contracts,
                                "sl_price": sl_price,
                                "tp_price": tp_price,
                                "raw_response": d
                            }
                        else:
                            s_msg = info.get("sMsg", "Order failed")
                            if s_code == "51010":
                                s_msg = "โปรดเปลี่ยนโหมดบัญชี OKX Demo เป็น 'Single-currency Margin' (⚙️ Settings -> Account Mode) เพื่อเปิดสิทธิ์เทรด Futures"
                            return {
                                "status": "API_ERROR",
                                "code": s_code,
                                "message": s_msg,
                                "raw_response": d
                            }
                    return {
                        "status": "API_ERROR",
                        "code": d.get("code"),
                        "message": d.get("msg", "OKX Order placement failed"),
                        "raw_response": d
                    }

            # 5-Stage Multi-Mode Robust Execution Pipeline
            stages = [
                # Stage 1: Isolated Hedge Mode + attached SL/TP
                {"instId": symbol, "tdMode": "isolated", "side": side_str, "posSide": pos_side, "ordType": "market", "sz": str(sz_contracts), "attachAlgoOrds": [algo_item] if algo_item else None},
                # Stage 2: Cross Margin Hedge Mode + attached SL/TP
                {"instId": symbol, "tdMode": "cross", "side": side_str, "posSide": pos_side, "ordType": "market", "sz": str(sz_contracts), "attachAlgoOrds": [algo_item] if algo_item else None},
                # Stage 3: Cross Margin Net Mode + attached SL/TP
                {"instId": symbol, "tdMode": "cross", "side": side_str, "ordType": "market", "sz": str(sz_contracts), "attachAlgoOrds": [algo_item] if algo_item else None},
                # Stage 4: Cross Margin Pure Market (No SL/TP, No posSide)
                {"instId": symbol, "tdMode": "cross", "side": side_str, "ordType": "market", "sz": str(sz_contracts)},
                # Stage 5: Isolated Margin Pure Market (No SL/TP, No posSide)
                {"instId": symbol, "tdMode": "isolated", "side": side_str, "ordType": "market", "sz": str(sz_contracts)}
            ]

            last_res = None
            for idx, stage_payload in enumerate(stages, 1):
                clean_payload = {k: v for k, v in stage_payload.items() if v is not None}
                res = _execute_order(clean_payload)
                if res.get("status") == "SUCCESS":
                    res["stage_success"] = idx
                    # Auto-submit attached Conditional TP/SL Algo Order to OKX Exchange
                    if (sl_price and float(sl_price) > 0) or (tp_price and float(tp_price) > 0):
                        algo_res = self.place_algo_tpsl_order(symbol, side, sz_contracts, sl_price=sl_price, tp_price=tp_price)
                        res["algo_order_res"] = algo_res
                    return res
                last_res = res

            return last_res if last_res else {"status": "ERROR", "message": "All execution stages failed"}
        except Exception as e:
            print(f"[OKXClient] Place order exception: {e}")
            return {"status": "ERROR", "message": str(e)}

    def place_algo_tpsl_order(self, symbol: str, side: str, sz_contracts: int, sl_price: float = None, tp_price: float = None, td_mode: str = "cross") -> dict:
        """
        Place Conditional TP/SL Algo Order directly on OKX Exchange API (POST /api/v5/trade/order-algo).
        Appears under 'Algo Orders' / 'Pending TP/SL' tab on OKX Demo Web UI!
        """
        self._resolve_keys()
        if not self.api_key or not self.api_secret or not self.passphrase:
            return {"status": "ERROR", "message": "OKX API Keys missing on server"}

        try:
            path = "/api/v5/trade/order-algo"
            url = f"{self.host}{path}"
            
            close_side = "sell" if side.upper() == "LONG" else "buy"
            pos_side = "long" if side.upper() == "LONG" else "short"
            
            payload = {
                "instId": symbol,
                "tdMode": td_mode,
                "side": close_side,
                "ordType": "conditional",
                "sz": str(sz_contracts)
            }
            if tp_price and float(tp_price) > 0:
                payload["tpTriggerPx"] = f"{float(tp_price):.4f}"
                payload["tpOrdPx"] = "-1"
                payload["tpTriggerPxType"] = "last"
            if sl_price and float(sl_price) > 0:
                payload["slTriggerPx"] = f"{float(sl_price):.4f}"
                payload["slOrdPx"] = "-1"
                payload["slTriggerPxType"] = "last"

            body = json.dumps(payload)
            headers = self._get_headers("POST", path, body)
            req = urllib.request.Request(url, data=body.encode('utf-8'), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                if data.get("code") == "0" and data.get("data"):
                    return {"status": "SUCCESS", "algoId": data["data"][0].get("algoId"), "raw_response": data}
                else:
                    return {"status": "API_ERROR", "code": data.get("code"), "message": data.get("msg", "Algo order failed"), "raw_response": data}
        except Exception as e:
            print(f"[OKXClient] Place algo order exception: {e}")
            return {"status": "ERROR", "message": str(e)}

    def place_spot_order(self, symbol: str, side: str, sz: float, val_usd: float = None, ord_type: str = "market") -> dict:
        """
        Place Spot Market Order on OKX Demo / Live API (POST /api/v5/trade/order).
        Supports Multi-Mode Robust Execution Pipeline (tdMode: 'cross' for Single-currency margin / 'cash' for Cash mode).
        Handles quote_ccy (USDT) for market BUY and base_ccy for market SELL.
        """
        self._resolve_keys()
        if not self.api_key or not self.api_secret or not self.passphrase:
            return {"status": "ERROR", "message": "OKX API Keys missing on server"}

        try:
            path = "/api/v5/trade/order"
            url = f"{self.host}{path}"
            
            clean_sym = symbol.replace("/", "-")
            if not clean_sym.endswith("-SWAP") and "-" not in clean_sym:
                clean_sym = f"{clean_sym}-USDT"
            spot_inst = clean_sym.replace("-SWAP", "")

            side_str = side.lower()
            
            # Format quantity
            if "BTC" in spot_inst:
                sz_coin_str = f"{float(sz):.4f}"
            elif "ETH" in spot_inst:
                sz_coin_str = f"{float(sz):.3f}"
            else:
                sz_coin_str = f"{float(sz):.2f}"

            usdt_amt_str = f"{float(val_usd):.2f}" if (val_usd and float(val_usd) > 0) else None

            def _execute_spot_payload(p_dict):
                b_str = json.dumps(p_dict)
                hdrs = self._get_headers("POST", path, b_str)
                req_obj = urllib.request.Request(url, data=b_str.encode('utf-8'), headers=hdrs, method="POST")
                with urllib.request.urlopen(req_obj, timeout=5) as resp:
                    d = json.loads(resp.read().decode())
                    if d.get("code") == "0" and d.get("data"):
                        info = d["data"][0]
                        s_code = str(info.get("sCode", "0"))
                        if s_code == "0":
                            return {
                                "status": "SUCCESS",
                                "order_id": info.get("ordId"),
                                "symbol": spot_inst,
                                "side": side_str,
                                "raw_response": d
                            }
                        else:
                            return {"status": "API_ERROR", "code": s_code, "message": info.get("sMsg", "Spot order failed"), "raw_response": d}
                    return {"status": "API_ERROR", "code": d.get("code"), "message": d.get("msg", "OKX Spot order failed"), "raw_response": d}

            # Multi-Stage Robust Spot Execution Pipeline:
            stages = []
            if side_str == "buy":
                if usdt_amt_str:
                    stages.append({"instId": spot_inst, "tdMode": "cross", "side": "buy", "ordType": "market", "sz": usdt_amt_str, "tgtCcy": "quote_ccy"})
                    stages.append({"instId": spot_inst, "tdMode": "cash", "side": "buy", "ordType": "market", "sz": usdt_amt_str, "tgtCcy": "quote_ccy"})
                stages.append({"instId": spot_inst, "tdMode": "cross", "side": "buy", "ordType": "market", "sz": sz_coin_str, "tgtCcy": "base_ccy"})
                stages.append({"instId": spot_inst, "tdMode": "cash", "side": "buy", "ordType": "market", "sz": sz_coin_str, "tgtCcy": "base_ccy"})
                stages.append({"instId": spot_inst, "tdMode": "cross", "side": "buy", "ordType": "market", "sz": sz_coin_str})
                stages.append({"instId": spot_inst, "tdMode": "cash", "side": "buy", "ordType": "market", "sz": sz_coin_str})
            else:
                stages.append({"instId": spot_inst, "tdMode": "cross", "side": "sell", "ordType": "market", "sz": sz_coin_str})
                stages.append({"instId": spot_inst, "tdMode": "cash", "side": "sell", "ordType": "market", "sz": sz_coin_str})
                stages.append({"instId": spot_inst, "tdMode": "cross", "side": "sell", "ordType": "market", "sz": sz_coin_str, "tgtCcy": "base_ccy"})
                stages.append({"instId": spot_inst, "tdMode": "cash", "side": "sell", "ordType": "market", "sz": sz_coin_str, "tgtCcy": "base_ccy"})

            last_res = None
            for idx, stage_p in enumerate(stages, 1):
                res = _execute_spot_payload(stage_p)
                if res.get("status") == "SUCCESS":
                    res["stage_success"] = idx
                    return res
                last_res = res

            return last_res if last_res else {"status": "ERROR", "message": "All spot stages failed"}
        except Exception as e:
            print(f"[OKXClient] Place spot order exception for {symbol}: {e}")
            return {"status": "ERROR", "message": str(e)}

    def get_positions(self, instType: str = "SWAP") -> dict:
        """Fetch active positions from OKX (GET /api/v5/account/positions)."""
        self._resolve_keys()
        if not self.api_key or not self.api_secret or not self.passphrase:
            return {"code": "-1", "msg": "Unconfigured OKX API Key", "data": []}

        try:
            path = f"/api/v5/account/positions?instType={instType}"
            url = f"{self.host}{path}"
            headers = self._get_headers("GET", path)
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            print(f"[OKXClient] Get positions exception: {e}")
            return {"code": "-1", "msg": str(e), "data": []}

    def close_position_on_okx(self, symbol: str, side: str, sz_contracts: int = None, td_mode: str = "cross") -> dict:
        self._resolve_keys()
        if not self.api_key or not self.api_secret or not self.passphrase:
            return {"status": "ERROR", "message": "OKX API Keys missing on server"}

        try:
            path_close = "/api/v5/trade/close-position"
            url_close = f"{self.host}{path_close}"
            pos_side = "long" if side.upper() == "LONG" else "short"
            
            # 1. Try Close-position without posSide (Net Mode) and with posSide (Long/Short Mode)
            close_payloads = [
                {"instId": symbol, "mgnMode": "cross"},
                {"instId": symbol, "mgnMode": "isolated"},
                {"instId": symbol, "mgnMode": "cross", "posSide": pos_side},
                {"instId": symbol, "mgnMode": "isolated", "posSide": pos_side},
                {"instId": symbol, "mgnMode": "cross", "posSide": "net"}
            ]
            
            for p in close_payloads:
                try:
                    b_str = json.dumps(p)
                    hdrs = self._get_headers("POST", path_close, b_str)
                    req_obj = urllib.request.Request(url_close, data=b_str.encode('utf-8'), headers=hdrs, method="POST")
                    with urllib.request.urlopen(req_obj, timeout=5) as resp:
                        data = json.loads(resp.read().decode())
                        if data.get("code") == "0":
                            return {"status": "SUCCESS", "symbol": symbol, "side": side, "raw_response": data}
                except Exception:
                    pass

            # 2. Fallback: Submit reduce-only market close order
            path_ord = "/api/v5/trade/order"
            url_ord = f"{self.host}{path_ord}"
            close_side = "sell" if side.upper() == "LONG" else "buy"
            sz_str = str(int(abs(sz_contracts))) if sz_contracts else "1"
            
            ord_payloads = [
                {"instId": symbol, "tdMode": "cross", "side": close_side, "ordType": "market", "sz": sz_str, "reduceOnly": True},
                {"instId": symbol, "tdMode": "isolated", "side": close_side, "ordType": "market", "sz": sz_str, "reduceOnly": True},
                {"instId": symbol, "tdMode": "cross", "side": close_side, "posSide": pos_side, "ordType": "market", "sz": sz_str, "reduceOnly": True}
            ]
            for p in ord_payloads:
                try:
                    b_str = json.dumps(p)
                    hdrs = self._get_headers("POST", path_ord, b_str)
                    req_obj = urllib.request.Request(url_ord, data=b_str.encode('utf-8'), headers=hdrs, method="POST")
                    with urllib.request.urlopen(req_obj, timeout=5) as resp:
                        data = json.loads(resp.read().decode())
                        if data.get("code") == "0":
                            return {"status": "SUCCESS", "symbol": symbol, "side": side, "raw_response": data}
                except Exception:
                    pass

            return {"status": "API_ERROR", "symbol": symbol, "message": "Failed to close position"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def get_pending_algo_orders(self, instType: str = "SWAP") -> dict:
        """Fetch pending TP/SL algo orders from OKX (GET /api/v5/trade/orders-algo-pending)."""
        self._resolve_keys()
        if not self.api_key or not self.api_secret or not self.passphrase:
            return {"code": "-1", "msg": "Unconfigured OKX API Key", "data": []}

        all_algos = []
        for o_type in ["conditional", "oco", "trigger"]:
            try:
                path = f"/api/v5/trade/orders-algo-pending?instType={instType}&ordType={o_type}"
                url = f"{self.host}{path}"
                headers = self._get_headers("GET", path)
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=4) as resp:
                    d = json.loads(resp.read().decode())
                    if d.get("code") == "0" and d.get("data"):
                        all_algos.extend(d.get("data", []))
            except Exception as e:
                print(f"[OKXClient] Error fetching algo orders ({o_type}): {e}")
        return {"code": "0", "msg": "SUCCESS", "data": all_algos}
