"""
OKX API v5 REST Client with Enterprise Authentication (V5 Signature).
Supports REST Endpoints for Market Data, Balance, Positions, Orders, Spot Trading, and Conditional TP/SL Algo Orders.
"""

import time
import json
import hmac
import base64
import hashlib
import urllib.request
import urllib.parse
import urllib.error
import os

CONTRACT_SIZES = {
    "BTC-USDT-SWAP": 0.01,
    "ETH-USDT-SWAP": 0.1,
    "SOL-USDT-SWAP": 1.0,
    "XRP-USDT-SWAP": 100.0,
    "DOGE-USDT-SWAP": 1000.0,
    "ADA-USDT-SWAP": 100.0,
    "LTC-USDT-SWAP": 1.0,
    "BCH-USDT-SWAP": 0.1,
    "LINK-USDT-SWAP": 1.0,
    "DOT-USDT-SWAP": 1.0,
    "ATOM-USDT-SWAP": 1.0,
    "ETC-USDT-SWAP": 1.0,
    "XLM-USDT-SWAP": 100.0,
    "TRX-USDT-SWAP": 1000.0,
    "AVAX-USDT-SWAP": 1.0,
    "BNB-USDT-SWAP": 0.1,
    "NEAR-USDT-SWAP": 1.0,
    "UNI-USDT-SWAP": 1.0,
    "FIL-USDT-SWAP": 1.0,
    "ALGO-USDT-SWAP": 100.0
}

class OKXClient:
    def __init__(self, api_key: str = None, api_secret: str = None, passphrase: str = None, simulated: bool = True):
        self.api_key = (api_key or os.getenv("OKX_API_KEY", "")).strip()
        self.api_secret = (api_secret or os.getenv("OKX_SECRET_KEY", "")).strip()
        self.passphrase = (passphrase or os.getenv("OKX_PASSPHRASE", "")).strip()
        self.simulated = simulated
        self.host = "https://www.okx.com"

    def _resolve_keys(self):
        if not self.api_key:
            self.api_key = os.getenv("OKX_API_KEY", "").strip()
        if not self.api_secret:
            self.api_secret = os.getenv("OKX_SECRET_KEY", "").strip()
        if not self.passphrase:
            self.passphrase = os.getenv("OKX_PASSPHRASE", "").strip()

    def _get_timestamp(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    def _sign(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        message = timestamp + method.upper() + request_path + body
        mac = hmac.new(self.api_secret.encode('utf-8'), message.encode('utf-8'), digestmod=hashlib.sha256)
        return base64.b64encode(mac.digest()).decode('utf-8')

    def _get_headers(self, method: str, request_path: str, body: str = "") -> dict:
        self._resolve_keys()
        ts = self._get_timestamp()
        sign = self._sign(ts, method, request_path, body) if self.api_secret else ""
        headers = {
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WebTraderBot/2.0"
        }
        if self.simulated:
            headers["x-simulated-trading"] = "1"
        return headers

    def get_candles(self, symbol: str = "BTC-USDT-SWAP", resolution: str = "240", limit: int = 300) -> list:
        try:
            bar_map = {
                "1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m",
                "60": "1H", "120": "2H", "240": "4H", "D": "1D", "1D": "1D"
            }
            bar_val = bar_map.get(str(resolution), "4H")
            path = f"/api/v5/market/candles?instId={symbol}&bar={bar_val}&limit={limit}"
            url = f"{self.host}{path}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            if self.simulated:
                headers["x-simulated-trading"] = "1"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                if data.get("code") == "0" and data.get("data"):
                    raw_candles = data["data"]
                    candles = []
                    for c in reversed(raw_candles):
                        candles.append({
                            "timestamp": int(c[0]),
                            "open": float(c[1]),
                            "high": float(c[2]),
                            "low": float(c[3]),
                            "close": float(c[4]),
                            "volume": float(c[5])
                        })
                    return candles
        except Exception as e:
            print(f"[OKXClient] Candles fetch exception for {symbol}: {e}")
        return []

    def get_account_balance(self) -> dict:
        self._resolve_keys()
        if not self.api_key or not self.api_secret or not self.passphrase:
            msg = f"OKX Demo API Key missing in Railway Variables"
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
                            if val is None or val == "":
                                return float(default)
                            return float(val)
                        except (ValueError, TypeError):
                            return float(default)

                    total_eq = safe_float(bal.get("totalEq"), 0.0)
                    iso_eq = safe_float(bal.get("isoEq"), 0.0)
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
        except Exception as e:
            return {"status": "FETCH_ERROR", "simulated": self.simulated, "message": str(e), "total_equity": None}

    def place_market_order(self, symbol: str, side: str, sz: float, sl_price: float = None, tp_price: float = None, td_mode: str = "cross") -> dict:
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
                            return {"status": "API_ERROR", "code": s_code, "message": s_msg, "raw_response": d}
                    return {"status": "API_ERROR", "code": d.get("code"), "message": d.get("msg", "OKX Order failed"), "raw_response": d}

            stages = [
                {"instId": symbol, "tdMode": "isolated", "side": side_str, "posSide": pos_side, "ordType": "market", "sz": str(sz_contracts), "attachAlgoOrds": [algo_item] if algo_item else None},
                {"instId": symbol, "tdMode": "cross", "side": side_str, "posSide": pos_side, "ordType": "market", "sz": str(sz_contracts), "attachAlgoOrds": [algo_item] if algo_item else None},
                {"instId": symbol, "tdMode": "cross", "side": side_str, "ordType": "market", "sz": str(sz_contracts), "attachAlgoOrds": [algo_item] if algo_item else None},
                {"instId": symbol, "tdMode": "cross", "side": side_str, "ordType": "market", "sz": str(sz_contracts)},
                {"instId": symbol, "tdMode": "isolated", "side": side_str, "ordType": "market", "sz": str(sz_contracts)}
            ]

            last_res = None
            for idx, stage_payload in enumerate(stages, 1):
                clean_payload = {k: v for k, v in stage_payload.items() if v is not None}
                res = _execute_order(clean_payload)
                if res.get("status") == "SUCCESS":
                    res["stage_success"] = idx
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
        self._resolve_keys()
        if not self.api_key or not self.api_secret or not self.passphrase:
            return {"status": "ERROR", "message": "OKX API Keys missing on server"}

        try:
            path = "/api/v5/trade/order-algo"
            url = f"{self.host}{path}"
            
            close_side = "sell" if side.upper() == "LONG" else "buy"
            
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
                pass
        return {"code": "0", "msg": "SUCCESS", "data": all_algos}
