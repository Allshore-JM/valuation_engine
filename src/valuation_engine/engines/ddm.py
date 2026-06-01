"""Dividend discount model — discounts expected dividends at the cost of equity.

Most appropriate for stable, dividend-paying firms (and the book's preferred route for
financial-service firms, where debt is raw material rather than financing). Yields a
per-share value directly. Typically a floor relative to FCFE when a firm pays out less
than it could afford.
"""
from __future__ import annotations

import pandas as pd

from valuation_engine.domain import Assumptions, Company
from valuation_engine.engines.base import (
    ValuationResult,
    phase_schedule,
    resolve_stable,
    terminal_value_warnings,
    trailing_dividend_per_share,
)


def value_ddm(company: Company, assumptions: Assumptions) -> ValuationResult:
    ke = assumptions.cost_of_equity
    if ke is None:
        raise ValueError("DDM needs assumptions.cost_of_equity")
    dps = trailing_dividend_per_share(company)
    if not dps:
        raise ValueError(
            f"{company.ticker}: no trailing dividends — DDM is not applicable; use FCFE/FCFF"
        )

    base_dps = dps
    schedule = phase_schedule(assumptions.phases)
    g_stable, _ = resolve_stable(assumptions, ke)

    rows: list[dict] = []
    pv_explicit = 0.0
    for year, name, g, _rr in schedule:
        dps *= 1.0 + g
        discount = 1.0 / (1.0 + ke) ** year
        pv = dps * discount
        pv_explicit += pv
        rows.append(
            {"year": year, "phase": name, "growth": g, "dividend_per_share": dps,
             "discount_factor": discount, "pv": pv}
        )

    last_year = schedule[-1][0] if schedule else 0
    dps_terminal = dps * (1.0 + g_stable)
    terminal_value = dps_terminal / (ke - g_stable)
    pv_terminal = terminal_value / (1.0 + ke) ** last_year
    value_per_share = pv_explicit + pv_terminal
    tv_share = pv_terminal / value_per_share if value_per_share else 0.0

    shares = company.shares_outstanding
    return ValuationResult(
        engine="DDM",
        value_per_share=value_per_share,
        discount_rate=ke,
        equity_value=value_per_share * shares if shares else None,
        firm_value=None,
        terminal_value=terminal_value,
        terminal_value_pv=pv_terminal,
        terminal_value_share=tv_share,
        projection=pd.DataFrame(rows),
        warnings=terminal_value_warnings(tv_share),
        inputs_used={"ke": ke, "base_dividend_per_share": base_dps, "stable_growth": g_stable},
    )
