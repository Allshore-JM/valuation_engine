"""Phase 5 reconciliation + report tests."""
from __future__ import annotations

import pytest

from valuation_engine.engines import baseline_assumptions
from valuation_engine.reconcile import (
    implied_growth,
    monte_carlo,
    scenario_analysis,
    tornado,
    triangulate,
)
from valuation_engine.report import render_html, render_report

TECH_PEERS = ["MSFT", "NVDA", "ORCL", "CRM", "AVGO"]


# -- triangulation -------------------------------------------------------------------
def test_triangulate_collects_intrinsic_and_relative(provider, aapl):
    peers = provider.get_peers(TECH_PEERS)
    tri = triangulate(aapl, baseline_assumptions(aapl), peers)
    methods = {e.method for e in tri.estimates}
    assert {"FCFF", "FCFE", "DDM"} <= methods
    assert any(m.startswith("relative:") for m in methods)
    assert tri.price == aapl.price
    assert tri.intrinsic_median and tri.relative_median and tri.overall_median
    # conservative DCF < price -> negative margin of safety
    assert tri.margin_of_safety is not None and tri.margin_of_safety < 0
    # every estimate has an upside vs price
    assert all(e.upside_vs_price is not None for e in tri.estimates)


def test_triangulate_without_peers_is_intrinsic_only(aapl):
    tri = triangulate(aapl, baseline_assumptions(aapl))
    assert tri.estimates and all(e.category == "intrinsic" for e in tri.estimates)
    assert tri.relative_median is None


# -- sensitivity ---------------------------------------------------------------------
def test_tornado_sorted_by_swing(aapl):
    bars = tornado(aapl, baseline_assumptions(aapl))
    assert bars
    swings = [b.swing for b in bars]
    assert swings == sorted(swings, reverse=True)
    assert all(b.swing >= 0 for b in bars)
    inputs = {b.input for b in bars}
    assert "cost_of_capital" in inputs and "phase_growth" in inputs


# -- scenarios -----------------------------------------------------------------------
def test_scenarios_ordered_bull_base_bear(aapl):
    bull, base, bear = scenario_analysis(aapl, baseline_assumptions(aapl))
    assert bull.name == "bull" and bear.name == "bear"
    assert bull.value_per_share > base.value_per_share > bear.value_per_share


# -- monte carlo ---------------------------------------------------------------------
def test_monte_carlo_is_deterministic_and_ordered(aapl):
    a = baseline_assumptions(aapl)
    first = monte_carlo(aapl, a, n=300, seed=42)
    second = monte_carlo(aapl, a, n=300, seed=42)
    assert first.median == second.median  # same seed -> identical
    assert first.p5 <= first.median <= first.p95
    assert 0.0 <= first.prob_value_above_price <= 1.0
    assert first.n == 300


def test_monte_carlo_different_seeds_differ(aapl):
    a = baseline_assumptions(aapl)
    assert monte_carlo(aapl, a, n=300, seed=1).median != monte_carlo(aapl, a, n=300, seed=2).median


# -- reverse DCF ---------------------------------------------------------------------
def test_implied_growth_recovers_price(aapl):
    a = baseline_assumptions(aapl)
    imp = implied_growth(aapl, a)
    # AAPL price ($312) far exceeds the conservative DCF value -> implied growth > assumed
    assert imp.implied_phase_growth > (imp.base_phase_growth or 0)
    assert imp.value_at_implied == pytest.approx(imp.price, rel=0.02)


# -- report --------------------------------------------------------------------------
def test_render_report_contains_all_sections(provider, aapl):
    peers = provider.get_peers(TECH_PEERS)
    md = render_report(aapl, baseline_assumptions(aapl), peers, mc_n=200, seed=0)
    for section in (
        "# Valuation report", "Not investment advice", "## Assumptions",
        "## Value estimates vs price", "## Sensitivity", "## Scenarios",
        "## Monte Carlo", "## Reverse DCF", "Margin of safety",
    ):
        assert section in md, section
    # staleness warning surfaces (ERP default is stale today)
    assert "STALE" in md
    # the disclaimer and a terminal-value note are present
    assert "Terminal value is" in md


def test_render_html_wraps_markdown(aapl):
    md = render_report(aapl, baseline_assumptions(aapl), run_monte_carlo=False)
    html = render_html(md, title="AAPL")
    assert html.startswith("<!doctype html>")
    assert "AAPL" in html and "<pre>" in html
