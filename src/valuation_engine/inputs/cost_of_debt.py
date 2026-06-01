"""Cost of debt via a synthetic rating from the interest-coverage ratio."""
from __future__ import annotations

import math

from valuation_engine.config.defaults import SYNTHETIC_RATING_TABLE
from valuation_engine.inputs.base import Estimate


def interest_coverage_ratio(ebit: float, interest_expense: float | None) -> float:
    """EBIT / interest expense; infinite when there is no interest burden."""
    if interest_expense is None or interest_expense <= 0:
        return math.inf
    return ebit / interest_expense


def synthetic_rating(coverage: float, table=None) -> tuple[str, float]:
    """Map an interest-coverage ratio to (rating, default_spread)."""
    table = table or SYNTHETIC_RATING_TABLE
    if coverage == math.inf:
        return table[0][2], table[0][3]
    for low, high, rating, spread in table:
        if low <= coverage < high:
            return rating, spread
    return table[-1][2], table[-1][3]  # below the lowest band -> distressed


def cost_of_debt(
    risk_free_rate: float,
    *,
    ebit: float | None = None,
    interest_expense: float | None = None,
    coverage: float | None = None,
    spread: float | None = None,
    tax_rate: float = 0.0,
) -> Estimate:
    """After-tax cost of debt: (rf + default spread) * (1 - tax).

    Supply ``spread`` directly, or a ``coverage`` ratio, or ``ebit`` + ``interest_expense``
    to derive a synthetic rating and its spread.
    """
    rating = None
    if spread is None:
        if coverage is None:
            if ebit is None or interest_expense is None:
                raise ValueError("provide spread, coverage, or (ebit and interest_expense)")
            coverage = interest_coverage_ratio(ebit, interest_expense)
        rating, spread = synthetic_rating(coverage)
    pretax = risk_free_rate + spread
    after_tax = pretax * (1.0 - tax_rate)
    cov_str = "inf" if coverage in (None, math.inf) else f"{coverage:.2f}"
    return Estimate(
        value=after_tax,
        rationale=(
            f"Cost of debt: rating {rating} (coverage {cov_str}) -> spread {spread:.2%}; "
            f"pretax {pretax:.3%}, after-tax {after_tax:.3%} at tax {tax_rate:.0%}."
        ),
        inputs_used={
            "coverage": None if coverage in (None, math.inf) else coverage,
            "rating": rating,
            "spread": spread,
            "pretax": pretax,
            "tax_rate": tax_rate,
        },
    )
