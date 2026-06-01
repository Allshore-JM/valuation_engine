"""Every input the valuation consumes — the audit surface of the engine.

The single most valuable feature of the tool is that *every* assumption here is
visible and overridable. Input modules (Phase 2) populate these fields and attach a
human-readable rationale for each; the consistency rules (stable g <= rf, stable
reinvestment = g / ROC, ...) are ENFORCED there, not in this pure data container.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GrowthPhase(BaseModel):
    """One stage of a multi-stage projection (high-growth -> transition -> stable).

    ``growth_rate`` may be supplied directly OR derived from fundamentals
    (``reinvestment_rate * return_on_capital`` for the firm, or
    ``retention * return_on_equity`` for equity). In the *stable* phase, growth must be
    derived / constrained, never free-floating — that rule is enforced by the input
    modules in Phase 2.
    """

    name: str
    years: int

    growth_rate: float | None = None
    reinvestment_rate: float | None = None
    return_on_capital: float | None = None  # ROC — firm-level (FCFF)
    return_on_equity: float | None = None  # ROE — equity-level (FCFE / DDM)
    operating_margin: float | None = None
    payout_ratio: float | None = None  # for DDM


class Assumptions(BaseModel):
    """The full set of valuation inputs for one company + one scenario."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    currency: str = "USD"
    marginal_tax_rate: float | None = None

    # Market-level inputs
    risk_free_rate: float | None = None  # long-term govt bond yield, cash-flow currency
    equity_risk_premium: float | None = None

    # Discount-rate building blocks
    beta: float | None = None  # levered (bottom-up) beta
    cost_of_equity: float | None = None  # CAPM: rf + beta * erp
    cost_of_debt_pretax: float | None = None  # rf + default spread
    cost_of_capital: float | None = None  # WACC, market-value weighted

    # Projection phases (high-growth, optional transition, stable).
    phases: list[GrowthPhase] = Field(default_factory=list)

    # Terminal / stable phase
    stable_growth_rate: float | None = None  # must be <= risk_free_rate
    stable_return_on_capital: float | None = None
    stable_reinvestment_rate: float | None = None  # = stable_growth / stable_ROC

    # Firm -> equity -> per-share bridge (value per share is more than equity / shares).
    value_of_options: float | None = None  # management / employee options to subtract
    noncontrolling_interest_value: float | None = None
    nonoperating_assets_value: float | None = None  # cross-holdings, excess cash

    # Audit trail: pinned manual overrides and per-input rationale strings.
    overrides: dict[str, float] = Field(default_factory=dict)
    rationales: dict[str, str] = Field(default_factory=dict)
