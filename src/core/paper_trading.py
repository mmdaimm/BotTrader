"""
Paper Trading Simulation Engine with Complete Quant Database, Trailing Stop, & 1.5x ATR TP
Simulates OKX Perpetual Futures order execution, leverage, dynamic Trailing SL/TP monitoring, and PnL calculations.
Automatically saves & restores state from data/paper_trading_state.json.
"""

import time
import json
import os
from src.core.risk_engine import RiskEngine

class PaperTradingEngine:
    def __init__(self, initial_capital: float = 10000.0, fee_pct: float = 0.0005, leverage: int = 3, storage_file: str = None):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.fee_pct = fee_pct  # OKX Futures fee (~0.05%)
        self.leverage = leverage  # Default 3x leverage
        self.risk_engine = RiskEngine(okx_fee_pct=fee_pct, leverage=leverage)
        self.active_positions = {}  # { symbol: position_dict }
        self.trade_history = []     # [ trade_dict ]
        
        # Disk Storage Setup
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        self.storage_file = storage_file or os.path.join(data_dir, "paper_trading_state.json")
        
        # Load existing state if available
        self._load_state()

    def _save_state(self):
        """Save balance, active positions, and trade history to JSON file."""
        try:
            state = {
                "initial_capital": self.initial_capital,
                "current_capital": self.current_capital,
                "leverage": self.leverage,
                "active_positions": self.active_positions,
                "trade_history": self.trade_history,
                "last_saved": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[PaperTradingEngine] Save state error: {e}")

    def _load_state(self):
        """Restore state from JSON file on server startup."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    self.initial_capital = state.get("initial_capital", self.initial_capital)
                    self.current_capital = state.get("current_capital", self.current_capital)
                    self.leverage = state.get("leverage", self.leverage)
                    self.active_positions = state.get("active_positions", {})
                    self.trade_history = state.get("trade_history", [])
                    print(f"[PaperTradingEngine] Restored paper trading state with Trailing Stop & 1.5x TP ({len(self.trade_history)} trades, {len(self.active_positions)} positions)")
            except Exception as e:
                print(f"[PaperTradingEngine] Load state error: {e}")

    def open_position(self, symbol: str, entry_price: float, risk_params: dict, side: str = "LONG", timeframe: str = "15m", market_snapshot: dict = None) -> dict:
        """
        Open a simulated Paper Trading position (LONG or SHORT) with 1.5x ATR TP and Trailing Stop.
        """
        if symbol in self.active_positions:
            return {"status": "SKIPPED", "reason": f"Position already active for {symbol}"}
            
        side = side.upper()
        qty = risk_params.get("position_qty", 0.0)
        
        if side == "LONG":
            sl_price = risk_params.get("sl_price", entry_price * 0.985)
            tp_price = risk_params.get("tp_price", entry_price * 1.015) # 1.5x ATR ~1.5%
        else: # SHORT
            sl_price = risk_params.get("sl_price", entry_price * 1.015)
            tp_price = risk_params.get("tp_price", entry_price * 0.985) # 1.5x ATR ~1.5%
            
        total_order_val = qty * entry_price
        margin_required = total_order_val / self.leverage
        
        if margin_required > self.current_capital:
            margin_required = self.current_capital
            total_order_val = margin_required * self.leverage
            qty = total_order_val / entry_price if entry_price > 0 else 0.0
            
        if qty <= 0 or total_order_val < 10.0:
            return {"status": "SKIPPED", "reason": "Insufficient capital for position sizing"}
            
        snapshot = market_snapshot or {}
        now_struct = time.localtime()
        
        position = {
            "id": f"PAPER-{int(time.time())}-{symbol}-{side}",
            "symbol": symbol,
            "side": side,
            "timeframe": timeframe,
            "leverage": self.leverage,
            "entry_price": entry_price,
            "qty": qty,
            "order_value": round(total_order_val, 2),
            "margin_required": round(margin_required, 2),
            "sl_price": round(sl_price, 4),
            "tp_price": round(tp_price, 4),
            "rr_ratio": risk_params.get("rr_ratio", 1.0),
            "trailing_active": False,
            "entry_timestamp": time.time(),
            "entry_time": time.strftime("%Y-%m-%d %H:%M:%S", now_struct),
            "day_of_week": time.strftime("%A", now_struct),
            "hour_of_day": now_struct.tm_hour,
            "status": "OPEN",
            "market_snapshot": {
                "ema200": snapshot.get("ema200", 0.0),
                "ema9": snapshot.get("ema9", 0.0),
                "ema21": snapshot.get("ema21", 0.0),
                "rsi": snapshot.get("rsi", 50.0),
                "adx": snapshot.get("adx", 20.0),
                "atr": snapshot.get("atr", 0.0),
                "volume_ratio": snapshot.get("volume_ratio", 1.0),
                "vwap": snapshot.get("vwap", entry_price)
            }
        }
        
        self.active_positions[symbol] = position
        self.current_capital -= margin_required
        
        self._save_state()
        return {"status": "SUCCESS", "position": position}

    def update_positions(self, pair_prices: dict) -> list:
        """Check active positions against current prices for Trailing Stop & TP/SL hits (LONG & SHORT)."""
        closed_trades = []
        state_changed = False
        
        for symbol in list(self.active_positions.keys()):
            pos = self.active_positions[symbol]
            current_price = pair_prices.get(symbol, {}).get("last_price")
            
            if not current_price:
                continue
                
            # Update Trailing Stop dynamically
            self.risk_engine.update_trailing_stop(pos, current_price)
            
            side = pos.get("side", "LONG")
            
            if side == "LONG":
                is_tp_hit = current_price >= pos["tp_price"]
                is_sl_hit = current_price <= pos["sl_price"]
            else: # SHORT
                is_tp_hit = current_price <= pos["tp_price"]
                is_sl_hit = current_price >= pos["sl_price"]
            
            if is_tp_hit or is_sl_hit:
                exit_type = f"{side} TP" if is_tp_hit else f"{side} SL"
                exit_price = pos["tp_price"] if is_tp_hit else pos["sl_price"]
                
                if side == "LONG":
                    gross_pnl = (exit_price - pos["entry_price"]) * pos["qty"]
                else:
                    gross_pnl = (pos["entry_price"] - exit_price) * pos["qty"]
                    
                fee = (exit_price * pos["qty"]) * self.fee_pct
                net_pnl = gross_pnl - fee
                
                return_amount = pos["margin_required"] + net_pnl
                self.current_capital += return_amount
                
                now_struct = time.localtime()
                holding_time_sec = int(time.time() - pos.get("entry_timestamp", time.time()))
                
                trade_record = {
                    "id": pos["id"],
                    "symbol": symbol,
                    "side": side,
                    "type": exit_type,
                    "timeframe": pos.get("timeframe", "15m"),
                    "leverage": pos.get("leverage", 3),
                    "entry_price": pos["entry_price"],
                    "exit_price": exit_price,
                    "qty": pos["qty"],
                    "order_value": pos["order_value"],
                    "margin_required": pos["margin_required"],
                    "sl_price": pos["sl_price"],
                    "tp_price": pos["tp_price"],
                    "net_pnl": round(net_pnl, 2),
                    "pnl_pct": round((net_pnl / pos["margin_required"]) * 100, 2),
                    "holding_duration_sec": holding_time_sec,
                    "holding_duration_formatted": f"{holding_time_sec // 60}m {holding_time_sec % 60}s",
                    "entry_time": pos["entry_time"],
                    "exit_time": time.strftime("%Y-%m-%d %H:%M:%S", now_struct),
                    "day_of_week": pos.get("day_of_week", time.strftime("%A", now_struct)),
                    "hour_of_day": pos.get("hour_of_day", now_struct.tm_hour),
                    "market_snapshot": pos.get("market_snapshot", {})
                }
                
                self.trade_history.insert(0, trade_record)
                closed_trades.append(trade_record)
                del self.active_positions[symbol]
                state_changed = True
                
        if state_changed:
            self._save_state()
            
        return closed_trades

    def get_summary(self) -> dict:
        """Return overall Paper Trading statistics."""
        win_trades = [t for t in self.trade_history if t["net_pnl"] > 0]
        total_trades = len(self.trade_history)
        win_rate = (len(win_trades) / total_trades * 100) if total_trades > 0 else 0.0
        net_profit = self.current_capital - self.initial_capital
        
        return {
            "initial_capital": self.initial_capital,
            "current_capital": round(self.current_capital, 2),
            "net_profit": round(net_profit, 2),
            "net_profit_pct": round((net_profit / self.initial_capital) * 100, 2),
            "total_trades": total_trades,
            "win_trades": len(win_trades),
            "loss_trades": total_trades - len(win_trades),
            "win_rate_pct": round(win_rate, 2),
            "active_positions_count": len(self.active_positions)
        }
