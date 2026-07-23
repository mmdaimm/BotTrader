"""
Telegram Bot Integration Module
Handles real-time alerts, order notifications, and /panic_stop commands.
"""

import urllib.request
import urllib.parse
import json
import os
import sys

class TelegramNotifier:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "8937104736:AAEqpaF5vg0i2c4M2a1udnWf_r4zKE5D7BQ")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "7489447597")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = None
        self._initialize_offset()

    def _initialize_offset(self):
        """Consume existing Telegram updates offset so old messages aren't re-processed as new commands."""
        url = f"{self.api_url}/getUpdates"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("ok") and res.get("result"):
                    updates = res.get("result", [])
                    if updates:
                        self.last_update_id = updates[-1]["update_id"]
        except Exception:
            pass

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read().decode("utf-8"))
                return res.get("ok", False)
        except Exception as e:
            print(f"[TelegramNotifier] Error sending message: {e}")
            return False

    def send_signal_alert(self, symbol: str, price: float, risk_params: dict):
        msg = (
            f"<b>🚀 WebTraderBot TRADE SIGNAL DETECTED!</b>\n\n"
            f"<b>Asset:</b> {symbol}\n"
            f"<b>Entry Price:</b> ${price:,.2f}\n"
            f"<b>Stop Loss:</b> ${risk_params.get('sl_price', 0):,.2f} (-${risk_params.get('sl_distance', 0):,.2f})\n"
            f"<b>Take Profit:</b> ${risk_params.get('tp_price', 0):,.2f} (+${risk_params.get('tp_distance', 0):,.2f})\n"
            f"<b>Risk-to-Reward:</b> 1:{risk_params.get('rr_ratio', 2.0)}\n"
            f"<b>Order Value:</b> ${risk_params.get('order_value', 0):,.2f}\n\n"
            f"<i>Strategy: Trend-Pullback Scalping (EMA 200/9/21 + RSI + ATR)</i>"
        )
        return self.send_message(msg)

    def send_panic_alert(self, reason: str = "Manual User Trigger"):
        msg = (
            f"<b>🚨 EMERGENCY PANIC STOP ACTIVATED!</b>\n\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Status:</b> All active orders cancelled & Bot trading locked."
        )
        return self.send_message(msg)

    def check_for_panic_command(self) -> bool:
        """Poll getUpdates to check if user sent NEW /panic_stop in Telegram chat."""
        offset_param = f"?offset={self.last_update_id + 1}" if self.last_update_id else ""
        url = f"{self.api_url}/getUpdates{offset_param}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read().decode("utf-8"))
                if res.get("ok"):
                    for result in res.get("result", []):
                        self.last_update_id = result["update_id"]
                        text = result.get("message", {}).get("text", "")
                        if text.strip() in ["/panic_stop", "/stop"]:
                            return True
        except Exception as e:
            print(f"[TelegramNotifier] Error checking updates: {e}")
        return False
