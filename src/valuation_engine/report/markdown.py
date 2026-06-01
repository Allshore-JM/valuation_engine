"""Render a full, auditable markdown valuation report.

Lists every assumption, all three intrinsic value estimates plus relative valuation,
over/under-valuation vs price, sensitivity, scenarios, Monte Carlo, the reverse-DCF
implied growth, and the terminal-value-dominance and staleness warnings.
"""
from __future__ import annotations

from datetime import date

from valuation_engine.config import all_staleness_warnings
from valuation_engine.domain import Assumptions, Company
from valuation_engine.engines import value_fcff
from valuation_engine.reconcile import (
    implied_growth,
    monte_carlo,
    scenario_analysis,
    tornado,
    triangulate,
)


def _pct(x: float | None, dp: int = 1) -> str:
    return f"{x:.{dp}%}" if x is not None else "—"


def _num(x: float | None, dp: int = 2) -> str:
    return f"{x:,.{dp}f}" if x is not None else "—"


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([line, sep, *body])


def render_report(
    company: Company,
    assumptions: Assumptions,
    peers=None,
    *,
    run_monte_carlo: bool = True,
    mc_n: int = 2000,
    seed: int = 0,
    today: date | None = None,
) -> str:
    a = assumptions
    out: list[str] = []
    out.append(f"# Valuation report — {company.name or company.ticker} ({company.ticker})")
    out.append("")
    out.append(
        "> **Not investment advice.** Every figure below is a model estimate driven by the "
        "assumptions listed here — change them and the answer changes. Garbage in, garbage "
        "out: treat a large gap between value and price as a prompt to re-examine the "
        "assumptions, not proof the market is wrong."
    )
    out.append("")
    out.append(
        f"- **Price:** {_num(company.price)} {company.currency or ''}  ·  "
        f"**Sector:** {company.sector or '—'}  ·  **Shares:** {_num(company.shares_outstanding, 0)}"
    )

    stale = all_staleness_warnings(today)
    if stale:
        out.append("")
        out.append("## ⚠️ Stale default inputs")
        out.extend(f"- {w}" for w in stale)

    # -- assumptions ----------------------------------------------------------------
    out.append("")
    out.append("## Assumptions")
    arows = [
        ["Marginal tax rate", _pct(a.marginal_tax_rate)],
        ["Risk-free rate", _pct(a.risk_free_rate)],
        ["Equity risk premium", _pct(a.equity_risk_premium)],
        ["Beta (levered)", _num(a.beta)],
        ["Cost of equity", _pct(a.cost_of_equity)],
        ["Pre-tax cost of debt", _pct(a.cost_of_debt_pretax)],
        ["WACC", _pct(a.cost_of_capital)],
        ["Stable growth", _pct(a.stable_growth_rate)],
        ["Stable ROC", _pct(a.stable_return_on_capital)],
    ]
    out.append(_md_table(["Input", "Value"], arows))
    out.append("")
    out.append("**Growth phases:**")
    prows = [
        [p.name, str(p.years), _pct(p.growth_rate), _pct(p.reinvestment_rate)]
        for p in a.phases
    ]
    out.append(_md_table(["Phase", "Years", "Growth", "Reinvestment"], prows))

    # -- triangulation --------------------------------------------------------------
    tri = triangulate(company, a, peers)
    out.append("")
    out.append("## Value estimates vs price")
    trows = [
        [e.method, _num(e.value_per_share), _pct(e.upside_vs_price)]
        for e in tri.estimates
    ]
    out.append(_md_table(["Method", "Value / share", "Upside vs price"], trows))
    out.append("")
    out.append(
        f"- Intrinsic median: **{_num(tri.intrinsic_median)}**  ·  "
        f"Relative median: **{_num(tri.relative_median)}**  ·  "
        f"Overall median: **{_num(tri.overall_median)}**"
    )
    out.append(
        f"- **Margin of safety** (intrinsic vs price): **{_pct(tri.margin_of_safety)}** "
        "(positive = price below value)"
    )

    # -- sensitivity ----------------------------------------------------------------
    bars = tornado(company, a)
    out.append("")
    out.append("## Sensitivity (one-at-a-time, FCFF value/share)")
    srows = [
        [b.input, f"{_num(b.low_input, 3)} → {_num(b.high_input, 3)}",
         _num(b.low_value), _num(b.high_value), _num(b.swing)]
        for b in bars
    ]
    out.append(_md_table(["Input", "Range", "Value @low", "Value @high", "Swing"], srows))

    # -- scenarios ------------------------------------------------------------------
    scen = scenario_analysis(company, a)
    out.append("")
    out.append("## Scenarios (FCFF)")
    scrows = [
        [s.name, _num(s.value_per_share), _pct(s.discount_rate),
         _pct(s.stable_growth_rate), _pct(s.phase_growth)]
        for s in scen
    ]
    out.append(_md_table(["Scenario", "Value / share", "Discount", "Stable g", "Phase g"], scrows))

    # -- monte carlo ----------------------------------------------------------------
    if run_monte_carlo:
        mc = monte_carlo(company, a, n=mc_n, seed=seed)
        out.append("")
        out.append(f"## Monte Carlo (FCFF, n={mc.n})")
        out.append(_md_table(
            ["p5", "p25", "median", "p75", "p95", "mean"],
            [[_num(mc.p5), _num(mc.p25), _num(mc.median), _num(mc.p75), _num(mc.p95), _num(mc.mean)]],
        ))
        out.append("")
        out.append(
            f"- P(value > price) = **{_pct(mc.prob_value_above_price)}**  ·  "
            f"P(value > 0) = {_pct(mc.prob_positive)}"
        )

    # -- reverse DCF ----------------------------------------------------------------
    try:
        imp = implied_growth(company, a)
        out.append("")
        out.append("## Reverse DCF — what the price implies")
        out.append(
            f"- Current price implies a high-growth-phase rate of "
            f"**{_pct(imp.implied_phase_growth)}** vs the assumed {_pct(imp.base_phase_growth)}."
            + (f" ({imp.note})" if imp.note else "")
        )
    except Exception as exc:  # noqa: BLE001
        out.append("")
        out.append(f"_Reverse DCF unavailable: {exc}_")

    # -- per-engine warnings + FCFF projection --------------------------------------
    fcff = value_fcff(company, a)
    if fcff.warnings:
        out.append("")
        out.append("## Warnings")
        out.extend(f"- {w}" for w in fcff.warnings)
        out.extend(f"- {w}" for w in tri.warnings if "terminal value" not in w)

    out.append("")
    out.append(
        f"_Terminal value is {(_pct(fcff.terminal_value_share))} of FCFF firm value; "
        f"firm value {_num(fcff.firm_value, 0)}, equity value {_num(fcff.equity_value, 0)}._"
    )
    out.append("")
    return "\n".join(out)
