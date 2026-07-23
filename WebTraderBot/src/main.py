"""
Main Application Entry Point for WebTraderBot Core Engine
"""

import sys
import os

# Set UTF-8 encoding for standard output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure src module is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.trader_bot import TraderBot

def main():
    print("==========================================================")
    print("WebTraderBot Core Engine - Sprint 1 Active")
    print("Strategy: Trend-Pullback Scalping (EMA 200/9/21 + RSI + ATR)")
    print("==========================================================")
    
    bot = TraderBot(symbol="THB_BTC", resolution="15", initial_capital=10000.0)
    result = bot.run_single_iteration()
    
    print(f"\n[Status]         : {result.get('status')}")
    print(f"[Last Price]     : ${result.get('last_price'):,.2f}")
    print(f"[Capital]        : ${result.get('capital'):,.2f}")
    print(f"[Signal Eval]    : {result.get('eval', {}).get('signal')}")
    print(f"[Signal Reason]  : {result.get('eval', {}).get('reason')}")
    
    if result.get("eval", {}).get("risk_params"):
        risk = result["eval"]["risk_params"]
        print("\n--- Position Sizing Risk Parameters ---")
        print(f"Entry Price      : ${risk['entry_price']:,.2f}")
        print(f"Stop Loss Price  : ${risk['sl_price']:,.2f} (-${risk['sl_distance']:,.2f})")
        print(f"Take Profit Price: ${risk['tp_price']:,.2f} (+${risk['tp_distance']:,.2f})")
        print(f"Risk-to-Reward   : 1:{risk['rr_ratio']}")
        print(f"Order Value      : ${risk['order_value']:,.2f}")

if __name__ == "__main__":
    main()
