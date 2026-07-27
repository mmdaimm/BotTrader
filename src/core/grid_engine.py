"""
Satellite Grid Trading Engine (Futures Market - 30% Capital Allocation)
Supports Arithmetic & Geometric Grids with Dynamic Bollinger Bands (20, 2.0 4H) Range
and Grid Density N spaced by 1.5 * ATR(14) 15m.
Enforces Out-of-Bounds Re-gridding Strategies:
- Price > Upper Bound: All USDT held -> ADX 4H < 25 (Re-grid shift up) / ADX 4H >= 25 (Trend Pause)
- Price < Lower Bound: 4H Close < Lower Bound - 2 * ATR(14) -> Liquidation Protection Cut
"""

import time
import math

class SatelliteGridEngine:
    def __init__(self, fee_rate: float = 0.0005, min_profit_grid: float = 0.003):
        self.fee_rate = fee_rate                # 0.05% Post-Only Maker Fee
        self.min_profit_grid = min_profit_grid  # 0.3% Minimum Profit per Grid
        self.grid_states = {}                   # { symbol: grid_info_dict }

    def calculate_arithmetic_grid(self, p_lower: float, p_upper: float, n: int) -> list:
        """
        Arithmetic Grid Formula:
        delta_p = (p_upper - p_lower) / n
        price_k = p_lower + k * delta_p
        """
        if n <= 0 or p_lower >= p_upper:
            return []
        delta_p = (p_upper - p_lower) / float(n)
        return [round(p_lower + k * delta_p, 4) for k in range(n + 1)]

    def calculate_geometric_grid(self, p_lower: float, p_upper: float, n: int) -> dict:
        """
        Geometric Grid Formula:
        r = (p_upper / p_lower) ** (1 / n)
        price_k = p_lower * (r ** k)
        G_profit = (r - 1) - 2 * fee_rate
        Reject configuration if G_profit < 0.003 (0.3%).
        """
        if n <= 0 or p_lower <= 0 or p_lower >= p_upper:
            return {"status": "INVALID", "reason": "Invalid grid bounds or N", "levels": []}

        r = (p_upper / float(p_lower)) ** (1.0 / float(n))
        g_profit = (r - 1.0) - (2.0 * self.fee_rate)

        if g_profit < self.min_profit_grid:
            return {
                "status": "REJECTED",
                "reason": f"Grid Profit Ratio {g_profit*100:.3f}% < Minimum Barrier {self.min_profit_grid*100:.1f}% (Fee Erosion Risk)",
                "g_profit": round(g_profit, 6),
                "levels": []
            }

        levels = [round(p_lower * (r ** k), 4) for k in range(n + 1)]
        return {
            "status": "ACCEPTED",
            "ratio_r": round(r, 6),
            "g_profit_pct": round(g_profit * 100.0, 3),
            "grid_count": n,
            "p_lower": p_lower,
            "p_upper": p_upper,
            "levels": levels
        }

    def determine_grid_bounds_and_density(self, bb_lower_4h: float, bb_upper_4h: float, atr_15m: float) -> tuple:
        """
        Calculate Dynamic Upper/Lower Bounds from Bollinger Bands (20, 2.0 4H)
        and Grid Density N spaced by 1.5 * ATR(14) 15m.
        """
        p_lower = bb_lower_4h
        p_upper = bb_upper_4h
        price_range = p_upper - p_lower

        grid_spacing = 1.5 * atr_15m if atr_15m > 0 else (price_range / 10.0)
        n = max(3, min(30, int(math.floor(price_range / grid_spacing))))

        return p_lower, p_upper, n

    def evaluate_out_of_bounds(self, symbol: str, current_price: float, p_lower: float, p_upper: float, adx_4h: float, atr_14: float) -> dict:
        """
        Out-of-Bounds & Re-gridding Decision Tree:
        1. Price > Upper Bound:
           - ADX 4H < 25 -> Re-grid Adjustment (Shift Upper Range Up: P_lower_new = P_upper_old)
           - ADX 4H >= 25 -> Switch to Trend Mode (Pause Grid Engine, hold USDT until ADX < 20)
        2. Price < Lower Bound:
           - Spot: Hold Base Asset
           - Futures: 4H Close < P_lower - 2 * ATR(14) -> Liquidation Protection Cut (Close Futures position)
        """
        if current_price > p_upper:
            if adx_4h < 25.0:
                # Sideway Range Shift Up
                p_lower_new = p_upper
                p_upper_new = round(p_upper + (p_upper - p_lower), 4)
                return {
                    "action": "REGRID_SHIFT_UP",
                    "status": "OOB_UPPER",
                    "p_lower_new": p_lower_new,
                    "p_upper_new": p_upper_new,
                    "reason": f"Price ${current_price:.4f} > Upper ${p_upper:.4f} & ADX {adx_4h:.1f} < 25 -> Re-grid Shift Up"
                }
            else:
                # Strong Uptrend Pause
                return {
                    "action": "PAUSE_TREND_UP",
                    "status": "STRONG_UPTREND",
                    "reason": f"Price ${current_price:.4f} > Upper ${p_upper:.4f} & ADX {adx_4h:.1f} >= 25 -> Pause Satellite (Strong Uptrend)"
                }

        elif current_price < p_lower:
            liq_cutoff = p_lower - (2.0 * atr_14)
            if current_price < liq_cutoff:
                return {
                    "action": "LIQUIDATION_PROTECTION_CUT",
                    "status": "OOB_LOWER_BREAKOUT",
                    "reason": f"4H Close ${current_price:.4f} < Cutoff ${liq_cutoff:.4f} (P_lower - 2x ATR) -> Emergency Futures Close"
                }
            else:
                p_lower_new = round(p_lower - (p_upper - p_lower), 4)
                p_upper_new = p_lower
                return {
                    "action": "REGRID_SHIFT_DOWN",
                    "status": "OOB_LOWER",
                    "p_lower_new": max(0.0001, p_lower_new),
                    "p_upper_new": p_upper_new,
                    "reason": f"Price ${current_price:.4f} < Lower ${p_lower:.4f} -> Re-grid Shift Down"
                }

        return {"action": "IN_BOUNDS", "status": "OK"}
