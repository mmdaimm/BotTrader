"""
Global State Manager & Strategy Exclusion Shield
- Enforces mutual exclusion between Strategy A (Trend) and Strategy B (Sideway Range) to avoid opposing orders
- Manages client order tagging (TP_15M_, SW_15M_, AR_SPOT_)
"""

import threading
import time
from typing import Dict, Any

class StateManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StateManager, cls).__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self):
        self.active_strategy_mode: Dict[str, str] = {}  # symbol -> "TREND" | "SIDEWAY" | "IDLE"
        self.active_order_tags: Dict[str, str] = {}    # order_id -> tag
        self.mode_locks = threading.Lock()

    def get_order_tag(self, strategy_type: str, symbol: str) -> str:
        """Generate client order tag for precise tracking (TP_15M_, SW_15M_, AR_SPOT_)."""
        tag_prefix = "TP_15M_"
        if strategy_type == "SIDEWAY_RANGE":
            tag_prefix = "SW_15M_"
        elif strategy_type == "ARBITRAGE":
            tag_prefix = "AR_SPOT_"
            
        clean_sym = symbol.replace("-", "").replace("USDT", "").replace("SWAP", "")
        return f"{tag_prefix}{clean_sym}_{int(time.time() * 1000) % 100000}"

    def acquire_strategy_lock(self, symbol: str, strategy: str) -> bool:
        """Enforce mutual exclusion: If Trend strategy is active, Sideway strategy cannot run for that symbol."""
        with self.mode_locks:
            current = self.active_strategy_mode.get(symbol, "IDLE")
            if current != "IDLE" and current != strategy:
                print(f"[StateManager] Strategy conflict on {symbol}: Cannot run {strategy} while {current} is active.")
                return False
            self.active_strategy_mode[symbol] = strategy
            return True

    def release_strategy_lock(self, symbol: str):
        """Release lock when position is closed."""
        with self.mode_locks:
            self.active_strategy_mode[symbol] = "IDLE"

    def get_status(self) -> Dict[str, Any]:
        """Return state snapshot."""
        with self.mode_locks:
            return {
                "active_strategy_modes": dict(self.active_strategy_mode),
                "active_order_tags_count": len(self.active_order_tags)
            }
