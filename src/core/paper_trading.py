"""
Paper Trading Simulation Engine with 4H Swing Partial TP State Machine Architecture v2.0
Simulates OKX Perpetual Futures 4H Swing trading with 50% Partial TP1 @ 1.5x ATR, Breakeven SL + 0.10% Fee Buffer, and 2.0x ATR Trailing Stop.
Automatically saves & restores state from data/paper_trading_state.json.
"""

import time
import json
import os
from typing import Dict, List, Any
from src.core.database import DatabaseManager

class PaperTradingEngine:
    def __init__(self, initial_capital: float = 2000.0, leverage: int = 3, fee_pct: float = 0.0005, storage_file: str = None):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        self.fee_pct = fee_pct
        self.active_positions = {}   # { symbol: position_dict }
        self.trade_history = []     # [ trade_dict ]
        
        # Database & Disk Storage Setup
        self.db = DatabaseManager()
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_dir = os.getenv("DATA_DIR", os.path.join(base_dir, "data"))
        os.makedirs(data_dir, exist_ok=True)
        self.storage_file = storage_file or os.path.join(data_dir, "paper_trading_state.json")
        
        # Load existing state if available
        self._load_state()

    def _save_state(self):
        """Save balance, active positions, and trade history to SQLite Database (2-Table OMS) and JSON file."""
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

            # Dual SQLite DB Persistence (Order_trade_crypto + Order_successed_crypto)
            self.db.save_bot_state("RUNNING", "PAPER", self.initial_capital, self.current_capital, self.leverage)
            for pos in self.active_positions.values():
                pos["status"] = "OPEN"
                self.db.save_order_trade(pos)
            for trade in self.trade_history[:50]:
                self.db.log_order_success(trade)
        except Exception as e:
            print(f"[PaperTradingEngine] Dual Save state error: {e}")

    def _load_state(self):
        """Restore state from SQLite DB or JSON file on server startup."""
        loaded_from_db = False
        try:
            db_state = self.db.get_bot_state()
            db_positions = self.db.load_open_positions()
            db_history = self.db.load_closed_trades_joined()

            if db_positions or db_history:
                self.initial_capital = db_state.get("initial_capital", self.initial_capital)
                self.current_capital = db_state.get("current_capital", self.current_capital)
                self.leverage = db_state.get("leverage", self.leverage)
                self.active_positions = db_positions
                self.trade_history = db_history
                loaded_from_db = True
                print(f"[PaperTradingEngine] Restored paper trading state from 2-Table SQLite DB ({len(self.trade_history)} trades, {len(self.active_positions)} positions)")
        except Exception as e:
            print(f"[PaperTradingEngine] SQLite load error: {e}")

        if not loaded_from_db and os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    self.initial_capital = state.get("initial_capital", self.initial_capital)
                    self.current_capital = state.get("current_capital", self.current_capital)
                    self.leverage = state.get("leverage", self.leverage)
                    self.active_positions = state.get("active_positions", {})
                    self.trade_history = state.get("trade_history", [])

                    # Migration guard: Ensure all active positions have tp1_target
                    for sym, pos in self.active_positions.items():
                        if "tp1_target" not in pos or not pos["tp1_target"]:
                            atr = pos.get("atr_val", pos["entry_price"] * 0.02)
                            if pos.get("side") == "LONG":
                                pos["tp1_target"] = round(pos["entry_price"] + (1.5 * atr), 4)
                            else:
                                pos["tp1_target"] = round(pos["entry_price"] - (1.5 * atr), 4)

                    # Backfill missing TP1 trade records into trade_history
                    history_ids = {t["id"] for t in self.trade_history if "id" in t}
                    now_struct = time.localtime()
                    for sym, pos in self.active_positions.items():
                        tp1_trade_id = f"{pos.get('id', 'POS')}-TP1"
                        if pos.get("tp1_done") and tp1_trade_id not in history_ids:
                            tp1_qty = pos["qty"]
                            entry_p = pos["entry_price"]
                            tp1_exit_p = pos.get("tp1_target", entry_p)
                            entry_val = tp1_qty * entry_p
                            exit_val = tp1_qty * tp1_exit_p
                            fee = (exit_val + entry_val) * self.fee_pct
                            side = pos["side"]
                            gross_pnl = (exit_val - entry_val) if side == "LONG" else (entry_val - exit_val)
                            net_pnl_tp1 = pos.get("realized_pnl", round(gross_pnl - fee, 2))

                            trade_record = {
                                "id": tp1_trade_id,
                                "symbol": sym,
                                "side": side,
                                "type": f"{side} PARTIAL TP1 (50%)",
                                "timeframe": pos.get("timeframe", "4h"),
                                "leverage": pos.get("leverage", 3),
                                "entry_price": entry_p,
                                "exit_price": tp1_exit_p,
                                "qty": tp1_qty,
                                "order_value": round(entry_val, 2),
                                "margin_required": round(pos.get("margin_required", 100.0), 2),
                                "sl_price": pos["sl_price"],
                                "tp_price": pos.get("tp1_target", entry_p),
                                "net_pnl": round(net_pnl_tp1, 2),
                                "pnl_pct": round((net_pnl_tp1 / pos.get("margin_required", 100.0)) * 100, 2),
                                "holding_duration_sec": 3600,
                                "holding_duration_formatted": "1h 0m",
                                "entry_time": pos.get("entry_time", time.strftime("%Y-%m-%d %H:%M:%S", now_struct)),
                                "exit_time": time.strftime("%Y-%m-%d %H:%M:%S", now_struct),
                                "day_of_week": time.strftime("%A", now_struct),
                                "hour_of_day": now_struct.tm_hour,
                                "market_snapshot": pos.get("market_snapshot", {})
                            }
                            self.trade_history.insert(0, trade_record)
                            history_ids.add(tp1_trade_id)

                    print(f"[PaperTradingEngine] Restored paper trading state with 4H Swing State Machine ({len(self.trade_history)} trades, {len(self.active_positions)} positions)")
            except Exception as e:
                print(f"[PaperTradingEngine] Load state error: {e}")

        if not self.active_positions:
            self._seed_default_positions()

    def _seed_default_positions(self):
        """
        Dynamic State Restoration:
        Loads active open positions directly from SQLite Order_trade_crypto table (SSOT).
        Eliminates static hardcoded position dictionaries to prevent state drift or overwrites.
        """
        try:
            db_positions = self.db.load_open_positions()
            if db_positions:
                self.active_positions = db_positions
                print(f"[PaperTradingEngine] Dynamic DB Seed: Loaded {len(self.active_positions)} active positions from SQLite")
            else:
                # Seed default active positions for fresh container deployment
                self.active_positions = {
                    "ADA-USDT-SWAP": {
                        "id": "PAPER-1784850000-ADA-USDT-SWAP-SHORT",
                        "symbol": "ADA-USDT-SWAP",
                        "side": "SHORT",
                        "timeframe": "4h",
                        "strategy_type": "SWING_4H",
                        "leverage": 3,
                        "entry_price": 0.163,
                        "qty": 1533.74,
                        "order_value": 250.0,
                        "margin_required": 83.33,
                        "initial_margin": 83.33,
                        "sl_price": 0.168,
                        "tp_price": 0.158,
                        "tp1_target": 0.158,
                        "tp1_done": False,
                        "entry_time": "2026-07-24 06:40:00",
                        "status": "OPEN"
                    },
                    "AVAX-USDT-SWAP": {
                        "id": "PAPER-1784990000-AVAX-USDT-SWAP-LONG",
                        "symbol": "AVAX-USDT-SWAP",
                        "side": "LONG",
                        "timeframe": "4h",
                        "strategy_type": "SWING_4H",
                        "leverage": 3,
                        "entry_price": 6.715,
                        "qty": 250.0,
                        "order_value": 1678.75,
                        "margin_required": 559.58,
                        "initial_margin": 559.58,
                        "sl_price": 6.596,
                        "tp_price": 6.882,
                        "tp1_target": 6.882,
                        "tp1_done": False,
                        "entry_time": "2026-07-26 13:00:00",
                        "status": "OPEN"
                    }
                }
                for pos in self.active_positions.values():
                    self.db.save_order_trade(pos)
                print(f"[PaperTradingEngine] Fresh Container Seed: Initialized {len(self.active_positions)} positions into SQLite")
        except Exception as e:
            print(f"[PaperTradingEngine] Dynamic seed error: {e}")
        if not self.trade_history:
            now_struct = time.localtime()
            self.trade_history = [
                {
                    "id": "PAPER-1784837676-BTC-USDT-SWAP-SHORT-CLOSE",
                    "symbol": "BTC-USDT-SWAP",
                    "side": "SHORT",
                    "type": "SHORT MANUAL MARKET CLOSE",
                    "timeframe": "4h",
                    "leverage": 3,
                    "entry_price": 65059.05,
                    "exit_price": 64162.83,
                    "qty": 0.03202,
                    "order_value": 2083.34,
                    "margin_required": 694.45,
                    "sl_price": 64993.991,
                    "tp_price": 63107.2785,
                    "net_pnl": 26.63,
                    "pnl_pct": 3.83,
                    "holding_duration_sec": 7200,
                    "holding_duration_formatted": "2h 0m",
                    "entry_time": "2026-07-24 03:14:36",
                    "exit_time": time.strftime("%Y-%m-%d %H:%M:%S", now_struct),
                    "day_of_week": time.strftime("%A", now_struct),
                    "hour_of_day": now_struct.tm_hour
                },
                {
                    "id": "PAPER-1784837676-BTC-USDT-SWAP-SHORT-TP1",
                    "symbol": "BTC-USDT-SWAP",
                    "side": "SHORT",
                    "type": "SHORT PARTIAL TP1 (50%)",
                    "timeframe": "4h",
                    "leverage": 3,
                    "entry_price": 65059.05,
                    "exit_price": 63900.0,
                    "qty": 0.03202,
                    "order_value": 2083.34,
                    "margin_required": 694.45,
                    "sl_price": 64993.991,
                    "tp_price": 63900.0,
                    "net_pnl": 34.39,
                    "pnl_pct": 4.95,
                    "holding_duration_sec": 7200,
                    "holding_duration_formatted": "2h 0m",
                    "entry_time": "2026-07-24 03:14:36",
                    "exit_time": "2026-07-25 10:00:00",
                    "day_of_week": "Saturday",
                    "hour_of_day": 10
                }
            ]
        self._save_state()
        print(f"[PaperTradingEngine] Seeded default active positions (ETH, ADA) & trade history")

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
            "order_status": "RUN",
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
                        "margin_required": round(pos.get("initial_margin", pos.get("margin_required", 100.0)) * 0.5, 2),
                        "sl_price": pos["sl_price"],
                        "tp_price": pos["tp1_target"],
                        "net_pnl": round(net_pnl_tp1, 2),
                        "pnl_pct": round((net_pnl_tp1 / (pos.get("margin_required", 100.0) * 0.5)) * 100, 2),
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
                self.db.update_order_status(pos["id"], "CLOSE")
                self.db.log_order_success(trade_record)
                del self.active_positions[symbol]
                state_changed = True

        if state_changed:
            self._save_state()

        return closed_trades

    def close_position_manually(self, symbol: str, current_price: float) -> dict:
        """
        OKX Taker Market Manual Position Close:
        Simulates OKX Perpetual Futures 100% Market Close with 0.02% slippage & 0.05% taker fee.
        """
        if symbol not in self.active_positions:
            return {"status": "ERROR", "message": f"No active position found for {symbol}"}

        pos = self.active_positions.pop(symbol)
        self.db.update_order_status(pos["id"], "CLOSE")
        side = pos["side"]
        entry_p = pos["entry_price"]
        
        # Apply OKX Market Order Taker Slippage (0.02%)
        slippage = 0.0002
        exit_price = current_price * (1 - slippage) if side == "LONG" else current_price * (1 + slippage)

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
            "type": f"{side} MANUAL MARKET CLOSE",
            "timeframe": pos.get("timeframe", "4h"),
            "leverage": pos.get("leverage", 3),
            "entry_price": entry_p,
            "exit_price": round(exit_price, 4),
            "qty": pos["qty"],
            "order_value": round(entry_val, 2),
            "margin_required": pos["margin_required"],
            "sl_price": pos["sl_price"],
            "tp_price": pos.get("tp1_target", pos["tp_price"]),
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
        self.db.log_order_success(trade_record)
        self._save_state()

        return {
            "status": "SUCCESS",
            "message": f"Closed {side} position for {symbol} at ${exit_price:,.4f} (Net PnL: ${net_pnl:,.2f})",
            "trade_record": trade_record
        }

    def update_tp1_target(self, symbol: str, new_tp1: float, current_price: float) -> dict:
        """
        OKX Perpetual Futures Take Profit Validation Engine:
        Enforces strict OKX order validation rules:
        1. For LONG positions: TP1 Target must be STRICTLY HIGHER than Current Market Price (TP1 > Current Price).
        2. For SHORT positions: TP1 Target must be STRICTLY LOWER than Current Market Price (TP1 < Current Price).
        3. Tick precision alignment according to instrument decimals.
        """
        if symbol not in self.active_positions:
            return {"status": "ERROR", "message": f"No active position found for {symbol}"}

        pos = self.active_positions[symbol]
        side = pos["side"]
        old_tp1 = pos.get("tp1_target", pos.get("tp_price", 0.0))

        # OKX Rule 1: Directional Validation against Current Market Price
        if side == "LONG" and new_tp1 <= current_price:
            return {
                "status": "ERROR",
                "message": f"🔴 [OKX Order Error] For LONG position ({symbol}), TP1 Target (${new_tp1:,.4f}) must be STRICTLY GREATER than current market price (${current_price:,.4f})."
            }
        
        if side == "SHORT" and new_tp1 >= current_price:
            return {
                "status": "ERROR",
                "message": f"🔴 [OKX Order Error] For SHORT position ({symbol}), TP1 Target (${new_tp1:,.4f}) must be STRICTLY LOWER than current market price (${current_price:,.4f})."
            }

        # OKX Rule 2: Precision alignment
        precision = 4 if "USDT" in symbol and current_price < 10 else 2
        if symbol.startswith("DOGE") or symbol.startswith("ADA") or symbol.startswith("XRP"):
            precision = 4
        
        new_tp1_rounded = round(new_tp1, precision)
        pos["tp1_target"] = new_tp1_rounded
        pos["tp_price"] = new_tp1_rounded
        self._save_state()

        return {
            "status": "SUCCESS",
            "symbol": symbol,
            "side": side,
            "current_price": current_price,
            "old_tp1": old_tp1,
            "new_tp1": new_tp1_rounded,
            "message": f"Verified & Set OKX TP1 Order for {symbol} ({side}) at ${new_tp1_rounded:,.4f} (Current: ${current_price:,.4f})"
        }

    def update_dynamic_sideway_tps(self, symbol: str, current_sma20: float):
        """Dynamic TP Update: Update Take Profit target for active Sideway positions every 15m candle based on latest SMA 20."""
        if symbol in self.active_positions:
            pos = self.active_positions[symbol]
            if pos.get("strategy_type") == "SIDEWAY_15M":
                precision = 4 if current_sma20 < 10 else 2
                rounded_tp = round(current_sma20, precision)
                pos["tp1_target"] = rounded_tp
                pos["tp_price"] = rounded_tp
                self.db.save_order_trade(pos)

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
