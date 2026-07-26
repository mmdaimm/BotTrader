"""
WebTraderBot Relational SQLite Database Manager
Implements 2-Table Normalized Order Management System Architecture with B-Tree Query Indexing:
1. Order_trade_crypto: Master order table (status = 'OPEN' / 'CLOSE', strategy_type = 'SWING_4H' / 'SIDEWAY_15M')
2. Order_successed_crypto: Execution history table (id_order = FK to Order_trade_crypto)
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
        # Enable Foreign Key enforcement in SQLite per connection
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        """Initialize 2-Table Normalized Order Schema & B-Tree High-Performance Indexes."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Global Bot Config Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_state_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    bot_state TEXT NOT NULL DEFAULT 'RUNNING',
                    trading_mode TEXT NOT NULL DEFAULT 'PAPER',
                    sideway_mode_enabled INTEGER NOT NULL DEFAULT 0,
                    sideway_state TEXT NOT NULL DEFAULT 'DISABLED',
                    initial_capital REAL NOT NULL DEFAULT 10000.0,
                    current_capital REAL NOT NULL DEFAULT 7250.0,
                    leverage INTEGER NOT NULL DEFAULT 3,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migration guard for bot_state_config
            cursor.execute("PRAGMA table_info(bot_state_config)")
            cols = [r[1] for r in cursor.fetchall()]
            if "sideway_mode_enabled" not in cols:
                cursor.execute("ALTER TABLE bot_state_config ADD COLUMN sideway_mode_enabled INTEGER NOT NULL DEFAULT 0")
            if "sideway_state" not in cols:
                cursor.execute("ALTER TABLE bot_state_config ADD COLUMN sideway_state TEXT NOT NULL DEFAULT 'DISABLED'")

            # 1. TABLE Order_trade_crypto (Master Order Table)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Order_trade_crypto (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    timeframe TEXT DEFAULT '4h',
                    strategy_type TEXT DEFAULT 'SWING_4H',
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
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    market_snapshot_json TEXT
                )
            """)

            # Migration guard for Order_trade_crypto
            cursor.execute("PRAGMA table_info(Order_trade_crypto)")
            order_cols = [r[1] for r in cursor.fetchall()]
            if "strategy_type" not in order_cols:
                cursor.execute("ALTER TABLE Order_trade_crypto ADD COLUMN strategy_type TEXT DEFAULT 'SWING_4H'")

            # 2. TABLE Order_successed_crypto (Execution & Settlement Table)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Order_successed_crypto (
                    id TEXT PRIMARY KEY,
                    id_order TEXT NOT NULL,
                    type TEXT NOT NULL,
                    exit_price REAL NOT NULL,
                    net_pnl REAL NOT NULL,
                    pnl_pct REAL NOT NULL,
                    holding_duration_sec INTEGER DEFAULT 0,
                    holding_duration_formatted TEXT,
                    exit_time TEXT NOT NULL,
                    day_of_week TEXT,
                    hour_of_day INTEGER,
                    FOREIGN KEY (id_order) REFERENCES Order_trade_crypto(id) ON DELETE CASCADE
                )
            """)

            # B-Tree Query Performance Indexing Optimization
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_status ON Order_trade_crypto(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_symbol ON Order_trade_crypto(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_strategy ON Order_trade_crypto(strategy_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_success_idorder ON Order_successed_crypto(id_order)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON system_audit_logs(event_type)")

            # Clean up old legacy tables if they exist
            cursor.execute("DROP TABLE IF EXISTS active_positions")
            cursor.execute("DROP TABLE IF EXISTS trade_history")

            # Table 4: Cashflow Logs
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

    def save_bot_state(self, bot_state: str, trading_mode: str, initial_capital: float, current_capital: float, leverage: int = 3, sideway_enabled: int = 0, sideway_state: str = "DISABLED"):
        """Save or update global bot configuration state."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bot_state_config (id, bot_state, trading_mode, sideway_mode_enabled, sideway_state, initial_capital, current_capital, leverage, last_updated)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    bot_state = excluded.bot_state,
                    trading_mode = excluded.trading_mode,
                    sideway_mode_enabled = excluded.sideway_mode_enabled,
                    sideway_state = excluded.sideway_state,
                    initial_capital = excluded.initial_capital,
                    current_capital = excluded.current_capital,
                    leverage = excluded.leverage,
                    last_updated = CURRENT_TIMESTAMP
            """, (bot_state, trading_mode, sideway_enabled, sideway_state, initial_capital, current_capital, leverage))
            conn.commit()

    def get_bot_state(self) -> Dict[str, Any]:
        """Fetch global bot state configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT * FROM bot_state_config WHERE id = 1").fetchone()
            if row:
                return dict(row)
            return {}

    def save_order_trade(self, pos: Dict[str, Any]):
        """Save or update an order record in Order_trade_crypto table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            snapshot_str = json.dumps(pos.get("market_snapshot", {}))
            cursor.execute("""
                INSERT INTO Order_trade_crypto (
                    id, symbol, side, timeframe, strategy_type, leverage, entry_price, qty, order_value,
                    margin_required, initial_margin, sl_price, tp_price, tp1_target,
                    tp1_done, realized_pnl, state, entry_time, status, market_snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                pos["id"], pos["symbol"], pos["side"], pos.get("timeframe", "4h"), pos.get("strategy_type", "SWING_4H"),
                pos.get("leverage", 3), pos["entry_price"], pos["qty"], pos["order_value"], pos["margin_required"],
                pos.get("initial_margin", pos["margin_required"]), pos["sl_price"],
                pos.get("tp_price", pos.get("tp1_target", 0.0)), pos.get("tp1_target", 0.0),
                1 if pos.get("tp1_done") else 0, pos.get("realized_pnl", 0.0),
                pos.get("state", "ST_OPEN_100"), pos["entry_time"], pos.get("status", "OPEN"),
                snapshot_str
            ))
            conn.commit()

    def update_order_status(self, pos_id: str, new_status: str = "CLOSE"):
        """Update status of an order in Order_trade_crypto (e.g. OPEN -> CLOSE)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Order_trade_crypto SET status = ? WHERE id = ? OR symbol = ?", (new_status, pos_id, pos_id))
            conn.commit()

    def log_order_success(self, trade: Dict[str, Any]):
        """Insert execution record into Order_successed_crypto table with foreign key resolution."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            id_order = trade.get("id_order", trade["id"].replace("-TP1", "").replace("-CLOSE", ""))
            
            # Relational Integrity Guard: Ensure master order exists in Order_trade_crypto
            master_exists = cursor.execute("SELECT id FROM Order_trade_crypto WHERE id = ?", (id_order,)).fetchone()
            if not master_exists:
                cursor.execute("""
                    INSERT INTO Order_trade_crypto (
                        id, symbol, side, timeframe, strategy_type, leverage, entry_price, qty, order_value,
                        margin_required, initial_margin, sl_price, tp_price, tp1_target, tp1_done,
                        realized_pnl, state, entry_time, status, market_snapshot_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO NOTHING
                """, (
                    id_order, trade.get("symbol", "UNKNOWN"), trade.get("side", "LONG"),
                    trade.get("timeframe", "4h"), trade.get("strategy_type", "SWING_4H"),
                    trade.get("leverage", 3), trade.get("entry_price", trade.get("exit_price", 0.0)),
                    trade.get("qty", 1.0), trade.get("order_value", 100.0), trade.get("margin_required", 33.3),
                    trade.get("margin_required", 33.3), trade.get("sl_price", 0.0), trade.get("tp_price", 0.0),
                    trade.get("tp_price", 0.0), 1, trade.get("net_pnl", 0.0), "ST_CLOSED",
                    trade.get("entry_time", trade.get("exit_time", "")), "CLOSE", "{}"
                ))

            cursor.execute("""
                INSERT OR REPLACE INTO Order_successed_crypto (
                    id, id_order, type, exit_price, net_pnl, pnl_pct,
                    holding_duration_sec, holding_duration_formatted,
                    exit_time, day_of_week, hour_of_day
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade["id"], id_order, trade["type"],
                trade["exit_price"], trade["net_pnl"], trade["pnl_pct"],
                trade.get("holding_duration_sec", 0), trade.get("holding_duration_formatted", ""),
                trade["exit_time"], trade.get("day_of_week", ""), trade.get("hour_of_day", 0)
            ))
            conn.commit()

    def load_open_positions(self) -> Dict[str, Dict[str, Any]]:
        """Load all active positions with status='OPEN' from Order_trade_crypto."""
        positions = {}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM Order_trade_crypto WHERE status = 'OPEN'").fetchall()
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

    def load_closed_trades_joined(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Load closed trade records joined between Order_successed_crypto and Order_trade_crypto."""
        history = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT 
                    s.id AS id,
                    s.id_order AS id_order,
                    t.symbol AS symbol,
                    t.side AS side,
                    s.type AS type,
                    t.timeframe AS timeframe,
                    t.strategy_type AS strategy_type,
                    t.leverage AS leverage,
                    t.entry_price AS entry_price,
                    s.exit_price AS exit_price,
                    t.qty AS qty,
                    t.order_value AS order_value,
                    t.margin_required AS margin_required,
                    t.sl_price AS sl_price,
                    t.tp1_target AS tp_price,
                    s.net_pnl AS net_pnl,
                    s.pnl_pct AS pnl_pct,
                    s.holding_duration_sec AS holding_duration_sec,
                    s.holding_duration_formatted AS holding_duration_formatted,
                    t.entry_time AS entry_time,
                    s.exit_time AS exit_time,
                    s.day_of_week AS day_of_week,
                    s.hour_of_day AS hour_of_day
                FROM Order_successed_crypto s
                JOIN Order_trade_crypto t ON s.id_order = t.id
                ORDER BY s.exit_time DESC
                LIMIT ?
            """
            rows = cursor.execute(query, (limit,)).fetchall()
            for r in rows:
                history.append(dict(r))
        return history

    def log_audit_event(self, event_type: str, message: str):
        """Record system audit log event."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO system_audit_logs (event_type, message) VALUES (?, ?)", (event_type, message))
            conn.commit()
