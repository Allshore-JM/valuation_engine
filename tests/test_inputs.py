"""Phase 2 input-module tests: formulas, edge cases, and an end-to-end chain on AAPL."""
from __future__ import annotations

import math
from datetime import date

import pytest

from valuation_engine.inputs import (
    bottom_up_beta,
    capitalize_rd,
    capm,
    cost_of_debt,
    effective_tax_rate,
    equity_risk_premium,
    fcfe,
    fcff,
    fundamental_growth_firm,
    implied_reinvestment_rate,
    interest_coverage_ratio,
    normalize_ebit,
    regression_beta,
    reinvestment_rate,
    relever_beta,
    risk_free_rate,
    synthetic_rating,
    terminal_value,
    unlever_beta,
    wacc,
)


# -- market-input estimates ----------------------------------------------------------
def test_risk_free_override_wins():
    e = risk_free_rate(0.05)
    assert e.value == 0.05
    assert "override" in e.rationale.lower()
    assert not e.warnings


def test_risk_free_default_staleness_propagates():
    fresh = risk_free_rate(today=date(2026, 5, 20))  # as_of 2026-05-15 -> 5 days
    assert fresh.value > 0 and not fresh.warnings
    stale = risk_free_rate(today=date(2026, 7, 1))  # 47 days
    assert any("STALE" in w for w in stale.warnings)


def test_erp_default_and_override():
    assert equity_risk_premium(0.055).value == 0.055
    assert equity_risk_premium(today=date(2026, 1, 2)).value > 0


# -- beta ----------------------------------------------------------------------------
def test_beta_unlever_relever_roundtrip():
    levered = 1.2
    unlevered = unlever_beta(levered, debt_to_equity=0.5, tax_rate=0.21)
    assert relever_beta(unlevered, 0.5, 0.21) == pytest.approx(levered)


def test_bottom_up_beta_no_debt_equals_unlevered():
    e = bottom_up_beta("Technology", debt=0, equity=100, tax_rate=0.21)
    assert e.value == pytest.approx(1.15)


def test_bottom_up_beta_unknown_sector_warns():
    e = bottom_up_beta("Nonexistent", debt=0, equity=100, tax_rate=0.21)
    assert e.value == pytest.approx(1.0)
    assert any("sector" in w for w in e.warnings)


def test_regression_beta_recovers_known_slope():
    market_returns = [0.01, -0.02, 0.03, 0.0, 0.015, -0.01, 0.02, 0.005]
    beta_true = 1.5

    def prices(returns):
        p = [100.0]
        for r in returns:
            p.append(p[-1] * (1 + r))
        return p

    e = regression_beta(prices([beta_true * r for r in market_returns]), prices(market_returns))
    assert e.value == pytest.approx(beta_true, rel=1e-6)


# -- cost of equity / debt / capital -------------------------------------------------
def test_capm():
    assert capm(0.04, 1.1, 0.05).value == pytest.approx(0.04 + 1.1 * 0.05)


def test_synthetic_rating_bands():
    assert synthetic_rating(10.0)[0].startswith("Aaa")
    assert synthetic_rating(math.inf)[0].startswith("Aaa")
    assert synthetic_rating(0.1)[0].startswith("D")
    rating, spread = synthetic_rating(3.5)  # band [3.00, 4.25)
    assert "A3" in rating and spread == pytest.approx(0.0122)


def test_interest_coverage_and_cost_of_debt():
    assert interest_coverage_ratio(1000, 0) == math.inf
    assert interest_coverage_ratio(1000, 200) == pytest.approx(5.0)
    # coverage 5.0 -> band [4.25,5.50) "A2/A" spread 0.0108
    e = cost_of_debt(0.04, ebit=1000, interest_expense=200, tax_rate=0.21)
    assert e.value == pytest.approx((0.04 + 0.0108) * (1 - 0.21))


def test_cost_of_debt_negative_ebit_is_distressed():
    e = cost_of_debt(0.04, ebit=-500, interest_expense=200, tax_rate=0.0)
    assert e.inputs_used["rating"].startswith("D")  # negative coverage -> distressed


def test_wacc_market_weights():
    e = wacc(cost_of_equity=0.10, after_tax_cost_of_debt=0.04, equity_value=800, debt_value=200)
    assert e.value == pytest.approx(0.10 * 0.8 + 0.04 * 0.2)


# -- earnings ------------------------------------------------------------------------
def test_capitalize_rd_steady_state():
    # Constant R&D of 100 with a 5-year life: research asset 300, amort 100, EBIT adj 0.
    r = capitalize_rd([100] * 6, rd_life_years=5)
    assert r.research_asset == pytest.approx(300.0)
    assert r.current_amortization == pytest.approx(100.0)
    assert r.ebit_adjustment == pytest.approx(0.0)


def test_capitalize_rd_growing_adds_back_to_ebit():
    # Growing R&D: current spend exceeds amortization of smaller past spend -> EBIT rises.
    r = capitalize_rd([200, 150, 100, 50, 25, 10], rd_life_years=5)
    assert r.ebit_adjustment > 0


def test_effective_tax_rate_normal_and_fallback():
    assert effective_tax_rate(210, 1000).value == pytest.approx(0.21)
    fallback = effective_tax_rate(0, -50, marginal=0.25)
    assert fallback.value == 0.25 and fallback.warnings


def test_normalize_ebit():
    e = normalize_ebit(1000, rd_adjustment=50, one_time_items=30)
    assert e.value == pytest.approx(1020)


# -- reinvestment / growth -----------------------------------------------------------
def test_fcff_formula():
    # NOPAT 750, net capex 200 -> FCFF 500
    assert fcff(1000, 0.25, capex=300, depreciation=100, change_in_working_capital=50).value == pytest.approx(500)


def test_fcfe_formula():
    # 500 - 75 + 40 = 465
    assert fcfe(500, interest_expense=100, tax_rate=0.25, net_debt_issued=40).value == pytest.approx(465)


def test_reinvestment_rate():
    assert reinvestment_rate(200, 50, 750).value == pytest.approx(250 / 750)


def test_fundamental_growth_and_implied_reinvestment():
    assert fundamental_growth_firm(0.40, 0.15).value == pytest.approx(0.06)
    assert implied_reinvestment_rate(0.03, 0.12).value == pytest.approx(0.25)


# -- terminal value ------------------------------------------------------------------
def test_terminal_value_gordon():
    e = terminal_value(100, 0.02, 0.08, risk_free_rate=0.04)
    assert e.value == pytest.approx(100 * 1.02 / (0.08 - 0.02))


def test_terminal_value_zero_growth_is_perpetuity():
    assert terminal_value(100, 0.0, 0.10).value == pytest.approx(1000)


def test_terminal_value_raises_when_growth_ge_rate():
    with pytest.raises(ValueError):
        terminal_value(100, 0.10, 0.08)


def test_terminal_value_raises_when_growth_exceeds_riskfree():
    with pytest.raises(ValueError):
        terminal_value(100, 0.05, 0.10, risk_free_rate=0.04)


def test_terminal_value_nonstrict_warns_instead_of_raising():
    e = terminal_value(100, 0.05, 0.10, risk_free_rate=0.04, strict=False)
    assert any("risk-free" in w for w in e.warnings)
    assert e.value > 0


# -- end-to-end chain on a real fixture ----------------------------------------------
def _latest_valid(statement, label):
    """Most recent non-null value for a row (yfinance leaves NaNs in the latest column)."""
    if label not in statement.index:
        return None
    series = statement.loc[label].dropna()
    return float(series.iloc[0]) if len(series) else None


def test_full_input_chain_on_aapl(aapl):
    inc = aapl.financials.income_statement
    ebit = _latest_valid(inc, "EBIT")
    interest = _latest_valid(inc, "InterestExpense")
    interest = abs(interest) if interest else None
    pretax = _latest_valid(inc, "PretaxIncome")
    tax_provision = _latest_valid(inc, "TaxProvision")

    tax = effective_tax_rate(tax_provision, pretax).value
    assert 0.0 < tax < 0.35

    coverage = interest_coverage_ratio(ebit, interest)
    kd = cost_of_debt(0.043, coverage=coverage, tax_rate=tax)
    beta = bottom_up_beta(aapl.sector, debt=aapl.total_debt, equity=aapl.market_cap, tax_rate=tax)
    ke = capm(0.043, beta.value, 0.045)
    w = wacc(ke.value, kd.value, equity_value=aapl.market_cap, debt_value=aapl.total_debt)

    assert 0.5 < beta.value < 2.5
    assert 0.0 < kd.value < ke.value  # debt is cheaper than equity
    assert 0.04 < w.value < 0.20
