"""Monte Carlo over the highest-leverage inputs -> value range + P(value > price).

Uses a seeded numpy Generator so a given seed reproduces the same distribution (tests
rely on this). Inputs are clamped to stay valid (g < discount rate, g <= rf), so every
draw produces a value and the sample count is deterministic.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
from pydantic import BaseModel

from valuation_engine.domain import Assumptions, Company
from valuation_engine.engines import value_fcff
from valuation_engine.reconcile.perturb import base_phase_growth, with_phase_growth, with_updates


class MonteCarloResult(BaseModel):
    n: int
    mean: float
    median: float
    p5: float
    p25: float
    p75: float
    p95: float
    price: float | None = None
    prob_value_above_price: float | None = None
    prob_positive: float = 1.0
    samples: list[float] | None = None


def monte_carlo(
    company: Company,
    assumptions: Assumptions,
    *,
    engine: Callable = value_fcff,
    n: int = 2000,
    seed: int = 0,
    price: float | None = None,
    sigma_discount: float = 0.01,
    sigma_stable_growth: float = 0.005,
    sigma_phase_growth: float = 0.03,
    sigma_tax: float = 0.03,
    keep_samples: bool = False,
) -> MonteCarloResult:
    rng = np.random.default_rng(seed)
    price = price if price is not None else company.price
    is_fcff = engine is value_fcff
    discount_field = "cost_of_capital" if is_fcff else "cost_of_equity"

    base_disc = getattr(assumptions, discount_field)
    base_sg = assumptions.stable_growth_rate
    base_pg = base_phase_growth(assumptions)
    base_tax = assumptions.marginal_tax_rate
    rf = assumptions.risk_free_rate

    values: list[float] = []
    for _ in range(n):
        disc = max(float(rng.normal(base_disc, sigma_discount)), 1e-3)
        updates = {discount_field: disc}
        if base_sg is not None:
            sg = float(rng.normal(base_sg, sigma_stable_growth))
            ceiling = min(disc - 1e-4, rf if rf is not None else disc - 1e-4)
            updates["stable_growth_rate"] = min(sg, ceiling)
        if base_tax is not None:
            updates["marginal_tax_rate"] = min(max(float(rng.normal(base_tax, sigma_tax)), 0.0), 0.6)
        a = with_updates(assumptions, **updates)
        if base_pg is not None:
            a = with_phase_growth(a, float(rng.normal(base_pg, sigma_phase_growth)))
        try:
            values.append(engine(company, a).value_per_share)
        except Exception:  # noqa: BLE001
            continue

    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise ValueError("Monte Carlo produced no valid samples")
    return MonteCarloResult(
        n=int(arr.size),
        mean=float(arr.mean()),
        median=float(np.median(arr)),
        p5=float(np.percentile(arr, 5)),
        p25=float(np.percentile(arr, 25)),
        p75=float(np.percentile(arr, 75)),
        p95=float(np.percentile(arr, 95)),
        price=price,
        prob_value_above_price=float((arr > price).mean()) if price else None,
        prob_positive=float((arr > 0).mean()),
        samples=arr.tolist() if keep_samples else None,
    )
