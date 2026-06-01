"""End-to-end orchestration: ticker -> Company -> Assumptions -> triangulation + report.

Shared by the CLI and any notebook/API caller. Every assumption is overridable: some
overrides feed the baseline computation (so they flow through cost of equity / debt /
WACC), others are pinned directly onto the finished Assumptions.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from valuation_engine.domain import Assumptions, Company
from valuation_engine.engines import baseline_assumptions
from valuation_engine.reconcile import Triangulation, triangulate
from valuation_engine.report import render_report

# Overrides that feed the baseline computation (flow through ke / kd / WACC).
_BASELINE_KEYS = ("rf", "erp", "tax", "high_growth", "high_growth_years", "stable_growth")
# Overrides pinned directly onto the finished Assumptions: override key -> field name.
_DIRECT_OVERRIDES = {
    "wacc": "cost_of_capital",
    "ke": "cost_of_equity",
    "kd_pretax": "cost_of_debt_pretax",
    "beta": "beta",
    "stable_roc": "stable_return_on_capital",
}


class ValuationRun(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    ticker: str
    price: float | None = None
    assumptions: Assumptions
    triangulation: Triangulation
    report_markdown: str
    margin_of_safety: float | None = None
    meets_threshold: bool | None = None
    company: Company


def run_valuation(
    ticker: str,
    provider,
    *,
    peers=None,
    peer_tickers=None,
    overrides: dict | None = None,
    today: date | None = None,
    run_monte_carlo: bool = True,
    mc_n: int = 2000,
    seed: int = 0,
    margin_of_safety_threshold: float | None = None,
) -> ValuationRun:
    overrides = dict(overrides or {})
    company = provider.get_company(ticker)

    baseline_kw = {k: overrides[k] for k in _BASELINE_KEYS if overrides.get(k) is not None}
    assumptions = baseline_assumptions(company, today=today, **baseline_kw)

    direct = {
        field: overrides[key]
        for key, field in _DIRECT_OVERRIDES.items()
        if overrides.get(key) is not None
    }
    if direct:
        assumptions = assumptions.model_copy(update=direct)

    if peers is None and peer_tickers:
        peers = provider.get_peers(list(peer_tickers))

    triangulation = triangulate(company, assumptions, peers)
    report_markdown = render_report(
        company, assumptions, peers,
        run_monte_carlo=run_monte_carlo, mc_n=mc_n, seed=seed, today=today,
    )

    meets = None
    if margin_of_safety_threshold is not None and triangulation.margin_of_safety is not None:
        meets = triangulation.margin_of_safety >= margin_of_safety_threshold

    return ValuationRun(
        ticker=ticker,
        price=company.price,
        assumptions=assumptions,
        triangulation=triangulation,
        report_markdown=report_markdown,
        margin_of_safety=triangulation.margin_of_safety,
        meets_threshold=meets,
        company=company,
    )
