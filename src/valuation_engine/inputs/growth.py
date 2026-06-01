"""Fundamental growth: growth earned through reinvestment and returns, not assumed."""
from __future__ import annotations

from valuation_engine.inputs.base import Estimate


def fundamental_growth_firm(reinvestment_rate: float, return_on_capital: float) -> Estimate:
    """Firm growth g = reinvestment rate * ROC."""
    g = reinvestment_rate * return_on_capital
    return Estimate(
        value=g,
        rationale=(
            f"Firm growth = reinvestment rate x ROC = {reinvestment_rate:.1%} x "
            f"{return_on_capital:.1%} = {g:.2%}."
        ),
        inputs_used={"reinvestment_rate": reinvestment_rate, "return_on_capital": return_on_capital},
    )


def fundamental_growth_equity(retention_ratio: float, return_on_equity: float) -> Estimate:
    """Equity growth g = retention ratio * ROE."""
    g = retention_ratio * return_on_equity
    return Estimate(
        value=g,
        rationale=(
            f"Equity growth = retention x ROE = {retention_ratio:.1%} x "
            f"{return_on_equity:.1%} = {g:.2%}."
        ),
        inputs_used={"retention_ratio": retention_ratio, "return_on_equity": return_on_equity},
    )


def implied_reinvestment_rate(growth: float, return_on_capital: float) -> Estimate:
    """Stable-phase reinvestment = g / ROC — keeps growth internally consistent."""
    if return_on_capital == 0:
        raise ValueError("return_on_capital is zero; implied reinvestment is undefined")
    rate = growth / return_on_capital
    return Estimate(
        value=rate,
        rationale=(
            f"Stable reinvestment = g/ROC = {growth:.2%}/{return_on_capital:.1%} = {rate:.1%} "
            "(consistent with the assumed stable growth)."
        ),
        inputs_used={"growth": growth, "return_on_capital": return_on_capital},
    )
