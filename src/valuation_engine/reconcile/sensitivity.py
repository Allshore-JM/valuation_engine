"""One-at-a-time sensitivity (tornado): vary high-leverage inputs, measure value swing."""
from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from valuation_engine.domain import Assumptions, Company
from valuation_engine.engines import value_fcff
from valuation_engine.reconcile.perturb import base_phase_growth, with_phase_growth, with_updates


class TornadoBar(BaseModel):
    input: str
    low_input: float
    high_input: float
    low_value: float
    high_value: float
    swing: float  # abs(high_value - low_value)


def tornado(
    company: Company,
    assumptions: Assumptions,
    *,
    engine: Callable = value_fcff,
) -> list[TornadoBar]:
    """Tornado bars sorted by the magnitude of value swing (most influential first)."""
    is_fcff = engine is value_fcff
    discount_field = "cost_of_capital" if is_fcff else "cost_of_equity"
    discount = getattr(assumptions, discount_field)
    rf = assumptions.risk_free_rate

    bars: list[TornadoBar] = []

    def add_scalar(name: str, low: float, high: float) -> None:
        try:
            lv = engine(company, with_updates(assumptions, **{name: low})).value_per_share
            hv = engine(company, with_updates(assumptions, **{name: high})).value_per_share
        except Exception:  # noqa: BLE001 - skip a bar that violates a constraint
            return
        bars.append(TornadoBar(input=name, low_input=low, high_input=high,
                               low_value=lv, high_value=hv, swing=abs(hv - lv)))

    if discount is not None:
        add_scalar(discount_field, max(discount - 0.01, 1e-4), discount + 0.01)
    if assumptions.stable_growth_rate is not None:
        g = assumptions.stable_growth_rate
        cap = min(rf if rf is not None else g + 0.005, (discount or 1.0) - 1e-4)
        add_scalar("stable_growth_rate", max(g - 0.005, -0.05), min(g + 0.005, cap))
    if assumptions.marginal_tax_rate is not None:
        t = assumptions.marginal_tax_rate
        add_scalar("marginal_tax_rate", max(t - 0.05, 0.0), min(t + 0.05, 0.6))

    pg = base_phase_growth(assumptions)
    if pg is not None:
        low, high = max(pg - 0.02, -0.5), pg + 0.02
        try:
            lv = engine(company, with_phase_growth(assumptions, low)).value_per_share
            hv = engine(company, with_phase_growth(assumptions, high)).value_per_share
            bars.append(TornadoBar(input="phase_growth", low_input=low, high_input=high,
                                   low_value=lv, high_value=hv, swing=abs(hv - lv)))
        except Exception:  # noqa: BLE001
            pass

    bars.sort(key=lambda b: b.swing, reverse=True)
    return bars
