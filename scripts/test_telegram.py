"""
Test Telegram Notification Script
"""

import sys
import os

# Set UTF-8 encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.telegram_bot import TelegramNotifier

def main():
    print("Testing Telegram Notifier Connection...")
    notifier = TelegramNotifier()
    
    welcome_msg = (
        "<b>🟢 WebTraderBot Telegram Connection Established!</b>\n\n"
        "สวัสดีครับคุณ Dai_M! ระบบ Telegram Bot ของ WebTraderBot เชื่อมต่อสำเร็จเรียบร้อยแล้ว\n\n"
        "📌 <b>ระบบพร้อมใช้งานสำหรับการแจ้งเตือน:</b>\n"
        "• 🚀 สัญญาณซื้อขาย (Trade Signal Alerts)\n"
        "• 💰 รายงานการทำกำไร/ตัดขาดทุน (TP/SL Reports)\n"
        "• 🚨 คำสั่งฉุกเฉิน <code>/panic_stop</code> เพื่อหยุดบอทได้ทันที"
    )
    
    success = notifier.send_message(welcome_msg)
    if success:
        print("✅ Telegram notification sent successfully to ID: 7489447597")
    else:
        print("❌ Failed to send Telegram message. Please check token or start the bot.")

if __name__ == "__main__":
    main()
