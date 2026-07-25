"""
WebTraderBot Relational SQLite Database Manager
Provides 100% permanent data persistence for active positions, trade history,
bot configuration, cash flow logs, and audit trails.
"""

import os
import sqlite3
import json
import time
from typing import Dict, List, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(PROJECT_ROOT, "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "trading_records.db")

class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize relational schema with 5 dedicated tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Table 1: Bot State Config
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_state_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    bot_state TEXT NOT NULL DEFAULT 'RUNNING',
                    trading_mode TEXT NOT NULL DEFAULT 'PAPER',
                    initial_capital REAL NOT NULL DEFAULT 10000.0,
                    current_capital REAL NOT NULL DEFAULT 7250.0,
                    leverage INTEGER NOT NULL DEFAULT 3,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table 2: Active Positions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_positions (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    timeframe TEXT DEFAULT '4h',
                    leverage INTEGER DEFAULT 3,
                    entry_price REAL NOT NULL,
                    qty REAL NOT NULL,
                    order_value REAL NOT NULL,
                    margin_required REAL NOT NULL,
                    initial_margin REAL NOT NULL,
                    sl_price REAL NOT NULL,
                    tp_price REAL NOT NULL,
                    tp1_target REAL NOT NULL,
                    tp1_done INTEGER DEFAULT 0,
                    realized_pnl REAL DEFAULT 0.0,
                    state TEXT DEFAULT 'ST_OPEN_100',
                    entry_time TEXT NOT NULL,
                    status TEXT DEFAULT 'OPEN',
                    market_snapshot_json TEXT
                )
            """)

            # Table 3: Trade History
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_history (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    type TEXT NOT NULL,
                    timeframe TEXT DEFAULT '4h',
                    leverage INTEGER DEFAULT 3,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    qty REAL NOT NULL,
                    order_value REAL NOT NULL,
                    margin_required REAL NOT NULL,
                    sl_price REAL NOT NULL,
                    tp_price REAL NOT NULL,
                    net_pnl REAL NOT NULL,
                    pnl_pct REAL NOT NULL,
                    holding_duration_sec INTEGER DEFAULT 0,
                    holding_duration_formatted TEXT,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    day_of_week TEXT,
                    hour_of_day INTEGER,
                    market_snapshot_json TEXT
                )
            """)

            # Table 4: Cashflow Logs (80% Funding Rate Arbitrage)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cashflow_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    daily_yield_usd REAL NOT NULL,
                    daily_yield_thb REAL NOT NULL,
                    annual_apy_pct REAL DEFAULT 15.33,
                    accumulated_total_usd REAL NOT NULL
                )
            """)

            # Table 5: System Audit Logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    def save_bot_state(self, bot_state: str, trading_mode: str, initial_capital: float, current_capital: float, leverage: int = 3):
        """Save or update global bot configuration state."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bot_state_config (id, bot_state, trading_mode, initial_capital, current_capital, leverage, last_updated)
                VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    bot_state = excluded.bot_state,
                    trading_mode = excluded.trading_mode,
                    initial_capital = excluded.initial_capital,
                    current_capital = excluded.current_capital,
                    leverage = excluded.leverage,
                    last_updated = CURRENT_TIMESTAMP
            """, (bot_state, trading_mode, initial_capital, current_capital, leverage))
            conn.commit()

    def get_bot_state(self) -> Dict[str, Any]:
        """Fetch global bot state configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT * FROM bot_state_config WHERE id = 1").fetchone()
            if row:
                return dict(row)
            return {}

    def save_active_position(self, pos: Dict[str, Any]):
        """Save or update an active position record in SQLite."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            snapshot_str = json.dumps(pos.get("market_snapshot", {}))
            cursor.execute("""
                INSERT INTO active_positions (
                    id, symbol, side, timeframe, leverage, entry_price, qty, order_value,
                    margin_required, initial_margin, sl_price, tp_price, tp1_target,
                    tp1_done, realized_pnl, state, entry_time, status, market_snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    qty = excluded.qty,
                    margin_required = excluded.margin_required,
                    sl_price = excluded.sl_price,
                    tp_price = excluded.tp_price,
                    tp1_target = excluded.tp1_target,
                    tp1_done = excluded.tp1_done,
                    realized_pnl = excluded.realized_pnl,
                    state = excluded.state,
                    status = excluded.status
            """, (
                pos["id"], pos["symbol"], pos["side"], pos.get("timeframe", "4h"), pos.get("leverage", 3),
                pos["entry_price"], pos["qty"], pos["order_value"], pos["margin_required"],
                pos.get("initial_margin", pos["margin_required"]), pos["sl_price"],
                pos.get("tp_price", pos.get("tp1_target", 0.0)), pos.get("tp1_target", 0.0),
                1 if pos.get("tp1_done") else 0, pos.get("realized_pnl", 0.0),
                pos.get("state", "ST_OPEN_100"), pos["entry_time"], pos.get("status", "OPEN"),
                snapshot_str
            ))
            conn.commit()

    def remove_active_position(self, pos_id: str):
        """Remove a closed position from SQLite active_positions table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM active_positions WHERE id = ? OR symbol = ?", (pos_id, pos_id))
            conn.commit()

    def log_trade(self, trade: Dict[str, Any]):
        """Insert a closed trade record into SQLite trade_history table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            snapshot_str = json.dumps(trade.get("market_snapshot", {}))
            cursor.execute("""
                INSERT OR REPLACE INTO trade_history (
                    id, symbol, side, type, timeframe, leverage, entry_price, exit_price,
                    qty, order_value, margin_required, sl_price, tp_price, net_pnl,
                    pnl_pct, holding_duration_sec, holding_duration_formatted,
                    entry_time, exit_time, day_of_week, hour_of_day, market_snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade["id"], trade["symbol"], trade["side"], trade["type"], trade.get("timeframe", "4h"),
                trade.get("leverage", 3), trade["entry_price"], trade["exit_price"], trade["qty"],
                trade["order_value"], trade["margin_required"], trade["sl_price"], trade["tp_price"],
                trade["net_pnl"], trade["pnl_pct"], trade.get("holding_duration_sec", 0),
                trade.get("holding_duration_formatted", ""), trade["entry_time"], trade["exit_time"],
                trade.get("day_of_week", ""), trade.get("hour_of_day", 0), snapshot_str
            ))
            conn.commit()

    def load_active_positions(self) -> Dict[str, Dict[str, Any]]:
        """Load all active positions from SQLite database."""
        positions = {}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM active_positions WHERE status = 'OPEN'").fetchall()
            for r in rows:
                d = dict(r)
                d["tp1_done"] = bool(d["tp1_done"])
                if d.get("market_snapshot_json"):
                    try:
                        d["market_snapshot"] = json.loads(d["market_snapshot_json"])
                    except Exception:
                        d["market_snapshot"] = {}
                positions[d["symbol"]] = d
        return positions

    def load_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Load closed trade records from SQLite database."""
        history = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM trade_history ORDER BY exit_time DESC LIMIT ?", (limit,)).fetchall()
            for r in rows:
                d = dict(r)
                if d.get("market_snapshot_json"):
                    try:
                        d["market_snapshot"] = json.loads(d["market_snapshot_json"])
                    except Exception:
                        d["market_snapshot"] = {}
                history.append(d)
        return history

    def log_audit_event(self, event_type: str, message: str):
        """Record system audit log event."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO system_audit_logs (event_type, message) VALUES (?, ?)", (event_type, message))
            conn.commit()
