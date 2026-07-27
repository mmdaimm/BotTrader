"""
Core Portfolio Rebalance Engine (Spot Market - 70% Capital Allocation)
Implements Shannon's Demon Volatility Harvesting & Dual-Factor Execution Triggers.
Dynamic Target Weighting:
- Bull / Normal Market: BTC 40% | ETH 30% | USDT 30%
- Bearish Market (BTC < EMA 200 1D): BTC 30% | ETH 20% | USDT 50%
"""

import time
import math

class CoreRebalanceEngine:
    def __init__(self, client=None, fee_rate: float = 0.0005, delta_rebalance: float = 0.05):
        self.client = client
        self.fee_rate = fee_rate                # 0.05% Post-Only Maker Fee
        self.delta_rebalance = delta_rebalance  # 5.0% Drift Threshold
        self.min_notional_map = {
            "BTC": 10.0,
            "ETH": 10.0,
            "USDT": 1.0
        }

    def get_target_weights(self, btc_price: float, btc_ema200_1d: float) -> dict:
        """
        Level 2 Guard: Dynamic Target Allocation Shift.
        - BTC >= EMA 200 (1D): BTC 40%, ETH 30%, USDT 30%
        - BTC < EMA 200 (1D): BTC 30%, ETH 20%, USDT 50% (Reduce Beta)
        """
        if btc_price < btc_ema200_1d:
            return {"BTC": 0.30, "ETH": 0.20, "USDT": 0.50}
        return {"BTC": 0.40, "ETH": 0.30, "USDT": 0.30}

    def calculate_core_value(self, btc_qty: float, btc_price: float, eth_qty: float, eth_price: float, usdt_cash: float) -> dict:
        """
        Calculate Total Core Portfolio Equity (V_core):
        V_core = sum(Q_i * P_i) + M_quote
        """
        btc_val = btc_qty * btc_price
        eth_val = eth_qty * eth_price
        v_core = btc_val + eth_val + usdt_cash

        if v_core <= 0:
            return {
                "v_core": 0.0,
                "weights": {"BTC": 0.0, "ETH": 0.0, "USDT": 1.0},
                "values": {"BTC": 0.0, "ETH": 0.0, "USDT": 0.0}
            }

        return {
            "v_core": round(v_core, 2),
            "weights": {
                "BTC": round(btc_val / v_core, 4),
                "ETH": round(eth_val / v_core, 4),
                "USDT": round(usdt_cash / v_core, 4)
            },
            "values": {
                "BTC": round(btc_val, 2),
                "ETH": round(eth_val, 2),
                "USDT": round(usdt_cash, 2)
            }
        }

    def evaluate_rebalance_trigger(self, asset: str, current_val: float, total_core_val: float, target_weight: float) -> dict:
        """
        Dual-Factor Execution Trigger Test:
        1. Threshold Test: | (Q_i * P_i) / V_core - W_target | >= delta_rebalance (5.0%)
        2. Cost-Benefit Filter: | V_target - V_current | > max(Min Notional, (2 * Fee / delta) * V_core)
        """
        if total_core_val <= 0:
            return {"triggered": False, "reason": "Zero Core Value"}

        current_weight = current_val / total_core_val
        weight_drift = abs(current_weight - target_weight)

        # Factor 1: Threshold Test
        if weight_drift < self.delta_rebalance:
            return {
                "triggered": False,
                "weight_drift": round(weight_drift, 4),
                "reason": f"Drift {weight_drift*100:.2f}% < Threshold {self.delta_rebalance*100:.1f}%"
            }

        target_val = total_core_val * target_weight
        val_diff = target_val - current_val
        abs_val_diff = abs(val_diff)

        # Factor 2: Cost-Benefit Filter
        min_notional = self.min_notional_map.get(asset, 10.0)
        fee_erosion_barrier = (2.0 * self.fee_rate / self.delta_rebalance) * total_core_val
        cost_benefit_barrier = max(min_notional, fee_erosion_barrier)

        if abs_val_diff <= cost_benefit_barrier:
            return {
                "triggered": False,
                "weight_drift": round(weight_drift, 4),
                "val_diff": round(val_diff, 2),
                "barrier": round(cost_benefit_barrier, 2),
                "reason": f"Order value ${abs_val_diff:.2f} <= Cost-Benefit Barrier ${cost_benefit_barrier:.2f}"
            }

        return {
            "triggered": True,
            "asset": asset,
            "action": "BUY" if val_diff > 0 else "SELL",
            "val_diff": round(val_diff, 2),
            "weight_drift": round(weight_drift, 4),
            "current_weight": round(current_weight, 4),
            "target_weight": round(target_weight, 4)
        }

    def process_rebalance(self, btc_qty: float, btc_price: float, eth_qty: float, eth_price: float, usdt_cash: float, btc_ema200_1d: float) -> dict:
        """
        Full Pipeline: Audit Portfolio -> Check Dynamic Targets -> Evaluate Dual-Factor Triggers.
        """
        core_audit = self.calculate_core_value(btc_qty, btc_price, eth_qty, eth_price, usdt_cash)
        v_core = core_audit["v_core"]
        target_weights = self.get_target_weights(btc_price, btc_ema200_1d)

        results = []
        for asset in ["BTC", "ETH"]:
            curr_val = core_audit["values"][asset]
            target_w = target_weights[asset]
            eval_res = self.evaluate_rebalance_trigger(asset, curr_val, v_core, target_w)
            if eval_res.get("triggered"):
                price = btc_price if asset == "BTC" else eth_price
                trade_qty = abs(eval_res["val_diff"]) / price
                eval_res["price"] = price
                eval_res["trade_qty"] = round(trade_qty, 6)
                results.append(eval_res)

        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "v_core": v_core,
            "macro_regime": "BEARISH_GUARD (USDT 50%)" if btc_price < btc_ema200_1d else "NORMAL_BULL (USDT 30%)",
            "current_weights": core_audit["weights"],
            "target_weights": target_weights,
            "rebalance_actions": results
        }
