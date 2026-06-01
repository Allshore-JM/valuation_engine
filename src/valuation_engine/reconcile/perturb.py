"""Helpers for perturbing Assumptions (used by sensitivity, scenarios, MC, implied)."""
from __future__ import annotations

from valuation_engine.domain import Assumptions


def with_updates(assumptions: Assumptions, **fields) -> Assumptions:
    """Return a copy of ``assumptions`` with top-level scalar fields replaced."""
    return assumptions.model_copy(update=fields)


def with_phase_growth(assumptions: Assumptions, new_growth: float) -> Assumptions:
    """Return a copy with the first (high-growth) phase's growth rate replaced."""
    if not assumptions.phases:
        return assumptions
    phases = list(assumptions.phases)
    phases[0] = phases[0].model_copy(update={"growth_rate": new_growth})
    return assumptions.model_copy(update={"phases": phases})


def base_phase_growth(assumptions: Assumptions) -> float | None:
    if not assumptions.phases:
        return None
    return assumptions.phases[0].growth_rate
