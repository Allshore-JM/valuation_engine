"""Weighted average cost of capital at market-value weights."""
from __future__ import annotations

from valuation_engine.inputs.base import Estimate


def wacc(
    cost_of_equity: float,
    after_tax_cost_of_debt: float,
    equity_value: float,
    debt_value: float,
) -> Estimate:
    """WACC = ke * E/V + kd_after_tax * D/V, with E and D at market value."""
    total = equity_value + debt_value
    if total <= 0:
        raise ValueError("equity_value + debt_value must be positive")
    weight_equity = equity_value / total
    weight_debt = debt_value / total
    value = cost_of_equity * weight_equity + after_tax_cost_of_debt * weight_debt
    return Estimate(
        value=value,
        rationale=(
            f"WACC = ke*E/V + kd(1-t)*D/V = {cost_of_equity:.3%}x{weight_equity:.1%} + "
            f"{after_tax_cost_of_debt:.3%}x{weight_debt:.1%} = {value:.3%} (market weights)."
        ),
        inputs_used={
            "weight_equity": weight_equity,
            "weight_debt": weight_debt,
            "ke": cost_of_equity,
            "kd_after_tax": after_tax_cost_of_debt,
        },
    )
