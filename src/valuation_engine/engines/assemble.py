"""Build a baseline ``Assumptions`` for a company from the Phase 2 input modules.

This is the bridge from inputs to engines: it wires risk-free rate, ERP, bottom-up beta,
CAPM cost of equity, synthetic-rating cost of debt and WACC, then derives a starting
phase structure from the firm's own history. Every field is overridable via keyword. The
Phase 6 pipeline reuses this; analysts are expected to tune the result.
"""
from __future__ import annotations

from datetime import date

from valuation_engine.domain import Assumptions, Company, GrowthPhase
from valuation_engine.engines.base import base_ebit, latest_valid
from valuation_engine.inputs import (
    bottom_up_beta,
    capm,
    effective_tax_rate,
    equity_risk_premium,
    interest_coverage_ratio,
    risk_free_rate,
    synthetic_rating,
    wacc,
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def baseline_assumptions(
    company: Company,
    *,
    rf: float | None = None,
    erp: float | None = None,
    today: date | None = None,
    tax: float | None = None,
    high_growth: float | None = None,
    high_growth_years: int = 5,
    stable_growth: float | None = None,
) -> Assumptions:
    fin = company.financials
    inc = fin.income_statement if fin else None
    bs = fin.balance_sheet if fin else None
    cf = fin.cash_flow if fin else None

    rf_v = risk_free_rate(rf, today=today).value
    erp_v = equity_risk_premium(erp, today=today).value

    if tax is None:
        tax = effective_tax_rate(
            latest_valid(inc, "TaxProvision") or 0.0,
            latest_valid(inc, "PretaxIncome") or 0.0,
        ).value

    beta = bottom_up_beta(
        company.sector, debt=company.total_debt or 0.0,
        equity=company.market_cap or 0.0, tax_rate=tax, today=today,
    ).value
    ke = capm(rf_v, beta, erp_v).value

    ebit = base_ebit(company)
    interest = latest_valid(inc, "InterestExpense")
    coverage = interest_coverage_ratio(ebit, abs(interest) if interest else None)
    _, spread = synthetic_rating(coverage)
    kd_pretax = rf_v + spread
    kd_after = kd_pretax * (1.0 - tax)

    wacc_v = wacc(ke, kd_after, equity_value=company.market_cap or 0.0,
                 debt_value=company.total_debt or 0.0).value

    # Historical reinvestment and return on capital -> a starting fundamental growth.
    nopat = ebit * (1.0 - tax)
    invested_capital = latest_valid(bs, "InvestedCapital")
    roc = (nopat / invested_capital) if invested_capital else wacc_v
    net_capex = abs(latest_valid(cf, "CapitalExpenditure") or 0.0) - (latest_valid(cf, "Depreciation") or 0.0)
    delta_wc = -(latest_valid(cf, "ChangeInWorkingCapital") or 0.0)  # cash-flow sign -> investment
    reinvestment = _clamp((net_capex + delta_wc) / nopat if nopat else 0.30, 0.0, 0.90)

    if high_growth is None:
        high_growth = _clamp(reinvestment * roc, 0.0, 0.20)
    if stable_growth is None:
        stable_growth = min(rf_v, 0.025)

    return Assumptions(
        currency=company.currency or "USD",
        marginal_tax_rate=tax,
        risk_free_rate=rf_v,
        equity_risk_premium=erp_v,
        beta=beta,
        cost_of_equity=ke,
        cost_of_debt_pretax=kd_pretax,
        cost_of_capital=wacc_v,
        phases=[GrowthPhase(
            name="high-growth", years=high_growth_years,
            growth_rate=high_growth, reinvestment_rate=reinvestment,
        )],
        stable_growth_rate=stable_growth,
        stable_return_on_capital=wacc_v,  # no excess returns in perpetuity (conservative)
    )
