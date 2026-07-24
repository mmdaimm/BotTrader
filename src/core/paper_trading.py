"""
Paper Trading Simulation Engine with 4H Swing Partial TP State Machine Architecture v2.0
Simulates OKX Perpetual Futures 4H Swing trading with 50% Partial TP1 @ 1.5x ATR, Breakeven SL + 0.10% Fee Buffer, and 2.0x ATR Trailing Stop.
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
                    print(f"[PaperTradingEngine] Restored paper trading state with 4H Swing State Machine ({len(self.trade_history)} trades, {len(self.active_positions)} positions)")
            except Exception as e:
                print(f"[PaperTradingEngine] Load state error: {e}")

    def open_position(self, symbol: str, entry_price: float, risk_params: dict, side: str = "LONG", timeframe: str = "4h", market_snapshot: dict = None) -> dict:
        """
        Open a simulated Paper Trading position with 4H Swing State Machine (ST_OPEN_100).
        """
        if symbol in self.active_positions:
            return {"status": "SKIPPED", "reason": f"Position already active for {symbol}"}
            
        side = side.upper()
        qty = risk_params.get("position_qty", 0.0)
        atr_val = market_snapshot.get("atr_4h", entry_price * 0.03) if market_snapshot else entry_price * 0.03
        
        if side == "LONG":
            sl_price = risk_params.get("sl_price", entry_price - (2.0 * atr_val))
            tp1_target = entry_price + (1.5 * atr_val)
        else: # SHORT
            sl_price = risk_params.get("sl_price", entry_price + (2.0 * atr_val))
            tp1_target = entry_price - (1.5 * atr_val)
            
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
            "initial_qty": qty,
            "order_value": round(total_order_val, 2),
            "margin_required": round(margin_required, 2),
            "initial_margin": round(margin_required, 2),
            "sl_price": round(sl_price, 4),
            "tp1_target": round(tp1_target, 4),
            "tp1_done": False,
            "state": "ST_OPEN_100",
            "atr_val": atr_val,
            "entry_timestamp": time.time(),
            "entry_time": time.strftime("%Y-%m-%d %H:%M:%S", now_struct),
            "day_of_week": time.strftime("%A", now_struct),
            "hour_of_day": now_struct.tm_hour,
            "status": "OPEN",
            "market_snapshot": {
                "ema50_4h": snapshot.get("ema50_4h", 0.0),
                "ema200_4h": snapshot.get("ema200_4h", 0.0),
                "supertrend": snapshot.get("supertrend", 0.0),
                "st_direction": snapshot.get("st_direction", "GREEN"),
                "adx": snapshot.get("adx", 20.0),
                "atr_4h": atr_val
            }
        }
        
        self.active_positions[symbol] = position
        self.current_capital -= margin_required
        
        self._save_state()
        return {"status": "SUCCESS", "position": position}

    def update_positions(self, pair_prices: dict) -> list:
        """
        Check active positions against current prices for 4H Swing State Machine:
        1. TP1 (50% Size @ 1.5x ATR): Partial Cash Flow Lock + Move SL to Breakeven (+0.10% Fee Buffer)
        2. Dynamic 2.0x ATR Trailing SL on remaining 50% Size
        3. Full Exit on SL hit or Supertrend Reversal
        """
        closed_trades = []
        state_changed = False
        
        for symbol in list(self.active_positions.keys()):
            pos = self.active_positions[symbol]
            item = pair_prices.get(symbol, {})
            current_price = item.get("last_price")
            eval_res = item.get("eval", {})
            st_direction = eval_res.get("market_snapshot", {}).get("st_direction", "GREEN")
            
            if not current_price:
                continue
                
            side = pos.get("side", "LONG")
            entry_p = pos["entry_price"]
            atr_val = pos.get("atr_val", current_price * 0.03)

            # Check 50% Partial TP1 Trigger (@ 1.5x ATR)
            if not pos.get("tp1_done", False):
                hit_tp1 = current_price >= pos["tp1_target"] if side == "LONG" else current_price <= pos["tp1_target"]
                if hit_tp1:
                    tp1_qty = pos["qty"] * 0.50
                    tp1_exit_p = pos["tp1_target"]
                    
                    entry_val = tp1_qty * entry_p
                    exit_val = tp1_qty * tp1_exit_p
                    fee = (exit_val + entry_val) * self.fee_pct
                    gross_pnl = (exit_val - entry_val) if side == "LONG" else (entry_val - exit_val)
                    net_pnl_tp1 = gross_pnl - fee

                    margin_returned = (pos["margin_required"] * 0.50) + net_pnl_tp1
                    self.current_capital += margin_returned

                    # Update remaining position state
                    pos["qty"] *= 0.50
                    pos["margin_required"] *= 0.50
                    pos["tp1_done"] = True
                    pos["realized_pnl"] = round(net_pnl_tp1, 2)
                    pos["state"] = "ST_RISK_FREE_50"

                    # Auto-Move SL to Breakeven (+0.10% Cover Fees Buffer)
                    be_sl = entry_p * 1.0010 if side == "LONG" else entry_p * 0.9990
                    pos["sl_price"] = round(be_sl, 4)

                    now_struct = time.localtime()
                    holding_time_sec = int(time.time() - pos.get("entry_timestamp", time.time()))

                    trade_record = {
                        "id": f"{pos['id']}-TP1",
                        "symbol": symbol,
                        "side": side,
                        "type": f"{side} PARTIAL TP1 (50%)",
                        "timeframe": pos.get("timeframe", "4h"),
                        "leverage": pos.get("leverage", 3),
                        "entry_price": entry_p,
                        "exit_price": tp1_exit_p,
                        "qty": tp1_qty,
                        "order_value": round(entry_val, 2),
                        "margin_required": round(pos["initial_margin"] * 0.5, 2),
                        "sl_price": pos["sl_price"],
                        "tp_price": pos["tp1_target"],
                        "net_pnl": round(net_pnl_tp1, 2),
                        "pnl_pct": round((net_pnl_tp1 / (pos["initial_margin"] * 0.5)) * 100, 2),
                        "holding_duration_sec": holding_time_sec,
                        "holding_duration_formatted": f"{holding_time_sec // 3600}h {(holding_time_sec % 3600) // 60}m",
                        "entry_time": pos["entry_time"],
                        "exit_time": time.strftime("%Y-%m-%d %H:%M:%S", now_struct),
                        "day_of_week": pos.get("day_of_week", time.strftime("%A", now_struct)),
                        "hour_of_day": now_struct.tm_hour,
                        "market_snapshot": pos.get("market_snapshot", {})
                    }
                    self.trade_history.insert(0, trade_record)
                    closed_trades.append(trade_record)
                    state_changed = True

            # Dynamic 2.0x ATR Trailing SL update on remaining position
            if side == "LONG":
                new_sl = round(current_price - (2.0 * atr_val), 4)
                if new_sl > pos["sl_price"]:
                    pos["sl_price"] = new_sl
            else: # SHORT
                new_sl = round(current_price + (2.0 * atr_val), 4)
                if new_sl < pos["sl_price"]:
                    pos["sl_price"] = new_sl

            # Check Exit Triggers (SL hit or Supertrend Reversal)
            is_sl_hit = current_price <= pos["sl_price"] if side == "LONG" else current_price >= pos["sl_price"]
            is_st_reversed = (st_direction == "RED") if side == "LONG" else (st_direction == "GREEN")

            if is_sl_hit or is_st_reversed:
                exit_type = f"{side} FULL EXIT (TP2)" if is_st_reversed else f"{side} SL"
                exit_price = pos["sl_price"] if is_sl_hit else current_price

                entry_val = pos["qty"] * entry_p
                exit_val = pos["qty"] * exit_price
                gross_pnl = (exit_val - entry_val) if side == "LONG" else (entry_val - exit_val)
                fee = (exit_val + entry_val) * self.fee_pct
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
                    "timeframe": pos.get("timeframe", "4h"),
                    "leverage": pos.get("leverage", 3),
                    "entry_price": entry_p,
                    "exit_price": exit_price,
                    "qty": pos["qty"],
                    "order_value": round(entry_val, 2),
                    "margin_required": pos["margin_required"],
                    "sl_price": pos["sl_price"],
                    "tp_price": pos.get("tp1_target", 0.0),
                    "net_pnl": round(net_pnl, 2),
                    "pnl_pct": round((net_pnl / pos["margin_required"]) * 100, 2),
                    "holding_duration_sec": holding_time_sec,
                    "holding_duration_formatted": f"{holding_time_sec // 3600}h {(holding_time_sec % 3600) // 60}m",
                    "entry_time": pos["entry_time"],
                    "exit_time": time.strftime("%Y-%m-%d %H:%M:%S", now_struct),
                    "day_of_week": pos.get("day_of_week", time.strftime("%A", now_struct)),
                    "hour_of_day": now_struct.tm_hour,
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
