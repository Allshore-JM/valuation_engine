"""FCFE / cost-of-equity model — values equity directly.

Derives free cash flow to equity from the firm's FCFF with a constant-debt-ratio
financing model: FCFE = FCFF - after-tax interest + net new debt, where debt grows with
the firm. This makes the two engines consistent by construction — for an unlevered firm
FCFE == FCFF and (with ke == WACC) the equity values are identical; for a lightly levered
firm they converge closely. Discounted at the cost of equity.
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


def value_fcfe(company: Company, assumptions: Assumptions) -> ValuationResult:
    ke = assumptions.cost_of_equity
    tax = assumptions.marginal_tax_rate
    if ke is None or tax is None:
        raise ValueError("FCFE needs assumptions.cost_of_equity and marginal_tax_rate")
    kd_pretax = assumptions.cost_of_debt_pretax or 0.0
    kd_after = kd_pretax * (1.0 - tax)

    nopat = base_ebit(company) * (1.0 - tax)
    debt = company.total_debt or 0.0
    schedule = phase_schedule(assumptions.phases)
    g_stable, rr_stable = resolve_stable(assumptions, ke)

    rows: list[dict] = []
    pv_explicit = 0.0
    for year, name, g, rr in schedule:
        nopat *= 1.0 + g
        fcff = nopat * (1.0 - rr)
        after_tax_interest = debt * kd_after  # interest on beginning-of-year debt
        net_debt_issued = debt * g  # debt grows with the firm (constant ratio)
        fcfe = fcff - after_tax_interest + net_debt_issued
        debt *= 1.0 + g
        discount = 1.0 / (1.0 + ke) ** year
        pv = fcfe * discount
        pv_explicit += pv
        rows.append(
            {"year": year, "phase": name, "growth": g, "fcff": fcff,
             "after_tax_interest": after_tax_interest, "net_debt_issued": net_debt_issued,
             "fcfe": fcfe, "discount_factor": discount, "pv": pv}
        )

    last_year = schedule[-1][0] if schedule else 0
    fcff_terminal = nopat * (1.0 + g_stable) * (1.0 - rr_stable)
    fcfe_terminal = fcff_terminal - debt * kd_after + debt * g_stable
    terminal_value = fcfe_terminal / (ke - g_stable)
    pv_terminal = terminal_value / (1.0 + ke) ** last_year
    operating_equity = pv_explicit + pv_terminal

    equity_value, per_share = finalize_equity(operating_equity, company, assumptions)
    tv_share = pv_terminal / operating_equity if operating_equity else 0.0

    return ValuationResult(
        engine="FCFE",
        value_per_share=per_share,
        discount_rate=ke,
        equity_value=equity_value,
        firm_value=None,
        terminal_value=terminal_value,
        terminal_value_pv=pv_terminal,
        terminal_value_share=tv_share,
        projection=pd.DataFrame(rows),
        warnings=terminal_value_warnings(tv_share),
        inputs_used={"ke": ke, "tax_rate": tax, "kd_pretax": kd_pretax,
                     "stable_growth": g_stable, "stable_reinvestment": rr_stable},
    )
