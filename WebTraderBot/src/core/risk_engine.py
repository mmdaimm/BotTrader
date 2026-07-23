"""
Risk Management Engine for OKX Futures
Position Sizing Calculator, Dynamic ATR SL/TP (LONG & SHORT), Trailing Stop, Breakeven SL, Isolated Margin.
"""

class RiskEngine:
    def __init__(self, max_risk_per_trade_pct: float = 0.015, okx_fee_pct: float = 0.0005, leverage: int = 3, max_consecutive_losses: int = 3):
        self.max_risk_pct = max_risk_per_trade_pct
        self.fee_pct = okx_fee_pct
        self.leverage = leverage
        self.max_losses = max_consecutive_losses
        self.consecutive_losses = 0
        self.is_circuit_broken = False

    def calculate_position_sizing(self, capital: float, entry_price: float, atr_val: float, side: str = "LONG", sl_multiplier: float = 1.5, tp_multiplier: float = 1.5) -> dict:
        """
        Calculate position size and dynamic ATR SL/TP levels for LONG and SHORT trades.
        Default TP Multiplier set to 1.5x ATR for fast scalp profit taking.
        """
        sl_distance = sl_multiplier * atr_val
        tp_distance = tp_multiplier * atr_val
        
        side = side.upper()
        if side == "LONG":
            sl_price = entry_price - sl_distance
            tp_price = entry_price + tp_distance
        else: # SHORT
            sl_price = entry_price + sl_distance
            tp_price = entry_price - tp_distance
            
        risk_amount = capital * self.max_risk_pct
        qty = risk_amount / sl_distance if sl_distance > 0 else 0.0
        total_order_val = qty * entry_price
        margin_required = total_order_val / self.leverage
        
        if margin_required > capital:
            margin_required = capital
            total_order_val = margin_required * self.leverage
            qty = total_order_val / entry_price if entry_price > 0 else 0.0
            
        return {
            "side": side,
            "entry_price": entry_price,
            "sl_price": round(sl_price, 4),
            "tp_price": round(tp_price, 4),
            "sl_distance": round(sl_distance, 4),
            "tp_distance": round(tp_distance, 4),
            "risk_amount": round(risk_amount, 2),
            "position_qty": qty,
            "order_value": round(total_order_val, 2),
            "margin_required": round(margin_required, 2),
            "leverage": self.leverage,
            "rr_ratio": round(tp_distance / sl_distance, 2) if sl_distance > 0 else 0
        }

    def update_trailing_stop(self, pos: dict, current_price: float) -> dict:
        """
        Trailing Stop Engine: Dynamically updates Stop Loss to lock in profits as market moves favorably.
        """
        side = pos.get("side", "LONG")
        entry = pos["entry_price"]
        sl = pos["sl_price"]
        
        if side == "LONG":
            # If price moves up by 1.0%, move SL to Breakeven (entry price)
            if current_price >= entry * 1.01 and sl < entry:
                pos["sl_price"] = round(entry, 4)
                pos["trailing_active"] = True
            # Trailing SL follows price up at a 1.0% distance
            new_sl = round(current_price * 0.99, 4)
            if pos.get("trailing_active") and new_sl > pos["sl_price"]:
                pos["sl_price"] = new_sl
        else: # SHORT
            # If price drops down by 1.0%, move SL to Breakeven (entry price)
            if current_price <= entry * 0.99 and sl > entry:
                pos["sl_price"] = round(entry, 4)
                pos["trailing_active"] = True
            # Trailing SL follows price down at a 1.0% distance
            new_sl = round(current_price * 1.01, 4)
            if pos.get("trailing_active") and new_sl < pos["sl_price"]:
                pos["sl_price"] = new_sl
                
        return pos

    def record_trade_result(self, is_win: bool):
        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.max_losses:
                self.is_circuit_broken = True

    def reset_circuit_breaker(self):
        self.consecutive_losses = 0
        self.is_circuit_broken = False
