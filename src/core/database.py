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

            # Core Portfolio State Table (70% Capital Spot Rebalance)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS core_rebalance_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    v_core REAL NOT NULL DEFAULT 7000.0,
                    macro_regime TEXT NOT NULL DEFAULT 'NORMAL_BULL',
                    weights_json TEXT,
                    last_rebalance_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Satellite Grid State Table (30% Capital Futures Geometric Grid)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS satellite_grid_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    grid_type TEXT NOT NULL DEFAULT 'GEOMETRIC',
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    p_lower REAL NOT NULL DEFAULT 0.0,
                    p_upper REAL NOT NULL DEFAULT 0.0,
                    grid_count INTEGER NOT NULL DEFAULT 10,
                    max_equity REAL NOT NULL DEFAULT 10000.0,
                    grid_orders_json TEXT,
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

            # 2. TABLE Order_successed_crypto (Execution & Settlement Log Table with FK)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Order_successed_crypto (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_order TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    qty REAL NOT NULL,
                    gross_pnl REAL NOT NULL,
                    fee REAL NOT NULL,
                    net_pnl REAL NOT NULL,
                    pnl_pct REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    FOREIGN KEY (id_order) REFERENCES Order_trade_crypto(id) ON DELETE CASCADE
                )
            """)

            # B-Tree Indexes for Query Performance (< 5ms retrieval)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_status ON Order_trade_crypto(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_symbol ON Order_trade_crypto(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_successed_id_order ON Order_successed_crypto(id_order)")
            
            # Seed bot_state_config if empty
            cursor.execute("SELECT COUNT(*) FROM bot_state_config")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO bot_state_config (id, bot_state, trading_mode, sideway_mode_enabled, sideway_state, initial_capital, current_capital, leverage)
                    VALUES (1, 'RUNNING', 'PAPER', 0, 'DISABLED', 10000.0, 7250.0, 3)
                """)

    def save_bot_state(self, bot_state: str, trading_mode: str, initial_capital: float, current_capital: float, leverage: int = 3, sideway_mode_enabled: int = 0, sideway_state: str = "DISABLED"):
        """Upsert global bot state configuration."""
        with self.get_connection() as conn:
            conn.execute("""
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
            """, (bot_state, trading_mode, sideway_mode_enabled, sideway_state, initial_capital, current_capital, leverage))

    def get_bot_state(self) -> Dict[str, Any]:
        """Fetch global bot state configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bot_state_config WHERE id = 1")
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {
                "bot_state": "RUNNING",
                "trading_mode": "PAPER",
                "sideway_mode_enabled": 0,
                "sideway_state": "DISABLED",
                "initial_capital": 10000.0,
                "current_capital": 7250.0,
                "leverage": 3
            }

    def save_active_position(self, pos: Dict[str, Any]):
        """Upsert active open position into Master Order Table (Order_trade_crypto)."""
        with self.get_connection() as conn:
            market_snapshot = json.dumps(pos.get("market_snapshot", {}))
            conn.execute("""
                INSERT INTO Order_trade_crypto (
                    id, symbol, side, timeframe, strategy_type, leverage, entry_price, qty, order_value,
                    margin_required, initial_margin, sl_price, tp_price, tp1_target, tp1_done,
                    realized_pnl, state, entry_time, status, market_snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
                ON CONFLICT(id) DO UPDATE SET
                    sl_price = excluded.sl_price,
                    tp1_target = excluded.tp1_target,
                    tp1_done = excluded.tp1_done,
                    realized_pnl = excluded.realized_pnl,
                    state = excluded.state,
                    market_snapshot_json = excluded.market_snapshot_json
            """, (
                pos["id"], pos["symbol"], pos["side"], pos.get("timeframe", "4h"), pos.get("strategy_type", "SWING_4H"),
                pos.get("leverage", 3), pos["entry_price"], pos["qty"], pos["order_value"],
                pos["margin_required"], pos.get("initial_margin", pos["margin_required"]),
                pos["sl_price"], pos.get("tp_price", pos.get("tp1_target", 0.0)),
                pos.get("tp1_target", pos.get("tp_price", 0.0)),
                1 if pos.get("tp1_done") else 0,
                pos.get("realized_pnl", 0.0), pos.get("state", "ST_OPEN_100"),
                pos.get("entry_time", time.strftime("%Y-%m-%d %H:%M:%S")),
                market_snapshot
            ))

    def close_active_position(self, order_id: str, closed_record: Dict[str, Any]):
        """
        Atomically close master order and record execution in history table (Order_successed_crypto).
        Enforces Database Transaction Isolation to prevent partial writes.
        """
        with self.get_connection() as conn:
            # 1. Update Master Order Status to 'CLOSE'
            conn.execute("""
                UPDATE Order_trade_crypto
                SET status = 'CLOSE', realized_pnl = ?
                WHERE id = ?
            """, (closed_record.get("net_pnl", 0.0), order_id))

            # 2. Insert Execution Record into Order_successed_crypto with Foreign Key
            conn.execute("""
                INSERT INTO Order_successed_crypto (
                    id_order, symbol, side, type, entry_price, exit_price, qty,
                    gross_pnl, fee, net_pnl, pnl_pct, entry_time, exit_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id, closed_record["symbol"], closed_record["side"], closed_record["type"],
                closed_record["entry_price"], closed_record["exit_price"], closed_record.get("qty", 1.0),
                closed_record.get("gross_pnl", closed_record.get("net_pnl", 0.0)),
                closed_record.get("fee", 0.0), closed_record["net_pnl"], closed_record["pnl_pct"],
                closed_record.get("entry_time", time.strftime("%Y-%m-%d %H:%M:%S")),
                closed_record.get("exit_time", time.strftime("%Y-%m-%d %H:%M:%S"))
            ))

    def load_active_positions(self) -> Dict[str, Dict[str, Any]]:
        """Load all OPEN positions indexed by symbol for memory reconciliation."""
        positions = {}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Order_trade_crypto WHERE status = 'OPEN'")
            for row in cursor.fetchall():
                pos = dict(row)
                pos["tp1_done"] = bool(pos["tp1_done"])
                if pos.get("market_snapshot_json"):
                    try:
                        pos["market_snapshot"] = json.loads(pos["market_snapshot_json"])
                    except Exception:
                        pos["market_snapshot"] = {}
                positions[pos["symbol"]] = pos
        return positions

    def load_closed_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Load recent execution history from Order_successed_crypto."""
        history = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM Order_successed_crypto
                ORDER BY id DESC LIMIT ?
            """, (limit,))
            for row in cursor.fetchall():
                history.append(dict(row))
        return history

    def clear_all_positions_and_history(self):
        """Purge all master orders and execution history."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM Order_successed_crypto")
            conn.execute("DELETE FROM Order_trade_crypto")
