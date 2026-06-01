"""FCFF / cost-of-capital model — values the whole firm, then bridges to equity.

Projects after-tax operating income (NOPAT) by phase, takes free cash flow to the firm
as NOPAT*(1 - reinvestment rate), discounts at the WACC, adds a Gordon terminal value,
then subtracts debt and adds cash to reach equity value. Best default for most firms.
"""
from __future__ import annotations

import pandas as pd

from valuation_engine.domain import Assumptions, Company
from valuation_engine.engines.base import (
    ValuationResult,
    base_ebit,
    finalize_equity,
    phase_schedule,
    resolve_stable,
    terminal_value_warnings,
)


def value_fcff(company: Company, assumptions: Assumptions) -> ValuationResult:
    wacc = assumptions.cost_of_capital
    tax = assumptions.marginal_tax_rate
    if wacc is None or tax is None:
        raise ValueError("FCFF needs assumptions.cost_of_capital and marginal_tax_rate")

    nopat = base_ebit(company) * (1.0 - tax)
    schedule = phase_schedule(assumptions.phases)
    g_stable, rr_stable = resolve_stable(assumptions, wacc)

    rows: list[dict] = []
    pv_explicit = 0.0
    for year, name, g, rr in schedule:
        nopat *= 1.0 + g
        fcff = nopat * (1.0 - rr)
        discount = 1.0 / (1.0 + wacc) ** year
        pv = fcff * discount
        pv_explicit += pv
        rows.append(
            {"year": year, "phase": name, "growth": g, "nopat": nopat,
             "reinvestment_rate": rr, "fcff": fcff, "discount_factor": discount, "pv": pv}
        )

    last_year = schedule[-1][0] if schedule else 0
    fcff_terminal = nopat * (1.0 + g_stable) * (1.0 - rr_stable)
    terminal_value = fcff_terminal / (wacc - g_stable)
    pv_terminal = terminal_value / (1.0 + wacc) ** last_year
    firm_value = pv_explicit + pv_terminal

    operating_equity = firm_value - (company.total_debt or 0.0)
    equity_value, per_share = finalize_equity(operating_equity, company, assumptions)
    tv_share = pv_terminal / firm_value if firm_value else 0.0

    return ValuationResult(
        engine="FCFF",
        value_per_share=per_share,
        discount_rate=wacc,
        equity_value=equity_value,
        firm_value=firm_value,
        terminal_value=terminal_value,
        terminal_value_pv=pv_terminal,
        terminal_value_share=tv_share,
        projection=pd.DataFrame(rows),
        warnings=terminal_value_warnings(tv_share),
        inputs_used={"wacc": wacc, "tax_rate": tax, "stable_growth": g_stable,
                     "stable_reinvestment": rr_stable},
    )
