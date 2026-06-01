"""Reverse DCF: what high-growth rate does the current market price imply?

Solves (by bisection, since value rises monotonically with growth) for the first-phase
growth rate that makes the engine's value per share equal the market price. A large gap
between the implied growth and the firm's fundamental growth is a prompt to re-examine
assumptions, not automatic proof the market is wrong.
"""
from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from valuation_engine.domain import Assumptions, Company
from valuation_engine.engines import value_fcff
from valuation_engine.reconcile.perturb import base_phase_growth, with_phase_growth


class ImpliedResult(BaseModel):
    implied_phase_growth: float
    base_phase_growth: float | None = None
    price: float
    value_at_implied: float
    note: str = ""


def implied_growth(
    company: Company,
    assumptions: Assumptions,
    *,
    engine: Callable = value_fcff,
    price: float | None = None,
    low: float = -0.50,
    high: float = 1.00,
    iterations: int = 80,
) -> ImpliedResult:
    price = price if price is not None else company.price
    if price is None:
        raise ValueError("no market price available to back out implied growth")
    if not assumptions.phases:
        raise ValueError("implied_growth needs at least one growth phase to solve over")

    def value_at(growth: float) -> float:
        return engine(company, with_phase_growth(assumptions, growth)).value_per_share

    base = base_phase_growth(assumptions)
    value_low, value_high = value_at(low), value_at(high)
    if price <= value_low:
        return ImpliedResult(implied_phase_growth=low, base_phase_growth=base, price=price,
                             value_at_implied=value_low,
                             note=f"price is at/below value even at {low:.0%} growth; market implies <= {low:.0%}")
    if price >= value_high:
        return ImpliedResult(implied_phase_growth=high, base_phase_growth=base, price=price,
                             value_at_implied=value_high,
                             note=f"price is at/above value even at {high:.0%} growth; market implies >= {high:.0%}")

    lo, hi = low, high
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        if value_at(mid) < price:
            lo = mid
        else:
            hi = mid
    growth = (lo + hi) / 2.0
    return ImpliedResult(implied_phase_growth=growth, base_phase_growth=base, price=price,
                         value_at_implied=value_at(growth))
