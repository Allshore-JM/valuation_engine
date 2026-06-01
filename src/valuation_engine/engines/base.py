"""Shared DCF plumbing: base-metric extraction, phase projection, the per-share bridge.

Every DCF engine reduces a stream of cash flows to an *operating equity value*, then the
single ``finalize_equity`` bridge adds cash and non-operating assets, subtracts minority
interest and the value of employee options, and divides by shares. Centralizing the
bridge is what lets FCFF and FCFE converge: the cash / options / minority treatment is
identical no matter which cash flow was discounted.
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, ConfigDict

from valuation_engine.domain import Assumptions, Company, GrowthPhase
from valuation_engine.inputs.terminal_value import stable_phase_checks
from valuation_engine.statements import latest_valid

# Flag terminal value when it dominates total value (far-future assumptions take over).
TERMINAL_VALUE_WARN_SHARE = 0.75


class ValuationResult(BaseModel):
    """Output of one DCF engine: the per-share value plus the full projection table."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    engine: str  # "FCFF" | "FCFE" | "DDM"
    value_per_share: float
    discount_rate: float
    equity_value: float | None = None
    firm_value: float | None = None
    terminal_value: float = 0.0
    terminal_value_pv: float = 0.0
    terminal_value_share: float = 0.0  # PV(TV) / total value
    projection: pd.DataFrame | None = None
    warnings: list[str] = []
    inputs_used: dict = {}


# -- base-metric extraction (latest_valid is imported from valuation_engine.statements) --
def base_ebit(company: Company) -> float:
    inc = company.financials.income_statement if company.financials else None
    ebit = latest_valid(inc, "EBIT")
    if ebit is None:
        ebit = latest_valid(inc, "OperatingIncome")
    if ebit is None:
        raise ValueError(f"{company.ticker}: no EBIT / OperatingIncome in financials")
    return ebit


def base_net_income(company: Company) -> float:
    inc = company.financials.income_statement if company.financials else None
    ni = latest_valid(inc, "NetIncome")
    if ni is None:
        raise ValueError(f"{company.ticker}: no NetIncome in financials")
    return ni


def trailing_dividend_per_share(company: Company, window_days: int = 365) -> float | None:
    div = company.dividends
    if div is None or len(div) == 0:
        return None
    last = div.index.max()
    recent = div[div.index >= last - pd.Timedelta(days=window_days)]
    total = float(recent.sum())
    return total if total > 0 else None


# -- phase resolution ----------------------------------------------------------------
def resolve_phase(phase: GrowthPhase) -> tuple[float, float]:
    """Resolve a phase to (growth, reinvestment_rate) from any two of g / RR / ROC."""
    g, rr, roc = phase.growth_rate, phase.reinvestment_rate, phase.return_on_capital
    if g is not None and rr is not None:
        return g, rr
    if g is not None and roc:
        return g, g / roc
    if rr is not None and roc is not None:
        return rr * roc, rr
    raise ValueError(
        f"phase {phase.name!r} underspecified: provide two of "
        "growth_rate, reinvestment_rate, return_on_capital"
    )


def phase_schedule(phases: list[GrowthPhase]) -> list[tuple[int, str, float, float]]:
    """Expand phases into a per-year schedule of (year, phase_name, growth, reinvest)."""
    schedule: list[tuple[int, str, float, float]] = []
    year = 0
    for phase in phases:
        g, rr = resolve_phase(phase)
        for _ in range(phase.years):
            year += 1
            schedule.append((year, phase.name, g, rr))
    return schedule


def resolve_stable(assumptions: Assumptions, discount_rate: float) -> tuple[float, float]:
    """Resolve and validate the stable phase, returning (growth, reinvestment_rate).

    Enforces the framework's discipline via ``stable_phase_checks`` (raises on g >= r or
    g > rf). Reinvestment defaults to g / ROC, with ROC defaulting to the discount rate
    (no excess returns in perpetuity).
    """
    g = assumptions.stable_growth_rate
    if g is None:
        raise ValueError("assumptions.stable_growth_rate is required")
    roc = assumptions.stable_return_on_capital or discount_rate
    if assumptions.stable_reinvestment_rate is not None:
        rr = assumptions.stable_reinvestment_rate
    else:
        rr = (g / roc) if roc else 0.0
    stable_phase_checks(
        g, discount_rate, risk_free_rate=assumptions.risk_free_rate, stable_roc=roc, strict=True
    )
    return g, rr


# -- firm/equity -> per share bridge -------------------------------------------------
def finalize_equity(
    operating_equity: float, company: Company, assumptions: Assumptions
) -> tuple[float, float]:
    """Operating equity value -> (total equity value, value per share).

    Adds cash + non-operating assets, subtracts minority interest, then subtracts the
    value of management/employee options before dividing by shares.
    """
    cash = company.cash_and_equivalents or 0.0
    nonop = assumptions.nonoperating_assets_value or 0.0
    minority = assumptions.noncontrolling_interest_value
    if minority is None:
        minority = company.minority_interest or 0.0
    options = assumptions.value_of_options or 0.0

    equity_value = operating_equity + cash + nonop - minority
    shares = company.shares_outstanding
    per_share = (equity_value - options) / shares if shares else float("nan")
    return equity_value, per_share


def terminal_value_warnings(tv_share: float) -> list[str]:
    if tv_share > TERMINAL_VALUE_WARN_SHARE:
        return [
            f"terminal value is {tv_share:.0%} of total value — the result rests heavily "
            "on far-future stable-phase assumptions"
        ]
    return []
