"""Bull / base / bear scenario analysis."""
from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from valuation_engine.domain import Assumptions, Company
from valuation_engine.engines import value_fcff
from valuation_engine.reconcile.perturb import base_phase_growth, with_phase_growth, with_updates


class ScenarioResult(BaseModel):
    name: str
    value_per_share: float | None
    discount_rate: float | None
    stable_growth_rate: float | None
    phase_growth: float | None


def scenario_analysis(
    company: Company,
    assumptions: Assumptions,
    *,
    engine: Callable = value_fcff,
) -> list[ScenarioResult]:
    """Bull (cheaper capital, faster growth), base, and bear (the reverse)."""
    is_fcff = engine is value_fcff
    discount_field = "cost_of_capital" if is_fcff else "cost_of_equity"
    base_disc = getattr(assumptions, discount_field) or 0.10
    base_sg = assumptions.stable_growth_rate or 0.0
    base_pg = base_phase_growth(assumptions) or 0.0
    rf = assumptions.risk_free_rate

    def build(name: str, d_disc: float, d_sg: float, d_pg: float) -> ScenarioResult:
        sg_cap = rf if rf is not None else base_sg + d_sg
        a = with_updates(
            assumptions,
            **{discount_field: max(base_disc + d_disc, 1e-4),
               "stable_growth_rate": min(base_sg + d_sg, sg_cap)},
        )
        a = with_phase_growth(a, max(base_pg + d_pg, -0.5))
        try:
            value = engine(company, a).value_per_share
        except Exception:  # noqa: BLE001
            value = None
        return ScenarioResult(
            name=name, value_per_share=value, discount_rate=getattr(a, discount_field),
            stable_growth_rate=a.stable_growth_rate, phase_growth=base_phase_growth(a),
        )

    return [
        build("bull", -0.01, +0.005, +0.03),
        build("base", 0.0, 0.0, 0.0),
        build("bear", +0.01, -0.005, -0.03),
    ]
