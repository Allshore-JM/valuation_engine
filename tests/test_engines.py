"""Phase 3 DCF-engine tests: exact synthetic cases, invariants, monotonicity, AAPL/KO."""
from __future__ import annotations

import pandas as pd
import pytest

from valuation_engine.domain import Assumptions, Company, Financials, GrowthPhase
from valuation_engine.engines import baseline_assumptions, value_ddm, value_fcfe, value_fcff
from valuation_engine.engines.base import resolve_phase, terminal_value_warnings


# -- synthetic builders --------------------------------------------------------------
def make_company(*, ebit=1000.0, net_income=800.0, debt=0.0, cash=0.0, shares=100.0,
                 dividends=None, minority=None) -> Company:
    col = pd.Timestamp("2025-12-31")
    inc = pd.DataFrame(
        {col: {"EBIT": ebit, "NetIncome": net_income, "InterestExpense": 0.0,
               "PretaxIncome": ebit, "TaxProvision": 0.0}}
    )
    fin = Financials(ticker="SYN", income_statement=inc)
    return Company(ticker="SYN", shares_outstanding=shares, total_debt=debt,
                   cash_and_equivalents=cash, minority_interest=minority,
                   dividends=dividends, financials=fin)


def make_assumptions(*, wacc=0.10, ke=0.10, kd_pretax=0.0, tax=0.25, phases=None,
                     stable_g=0.02, stable_roc=0.10, stable_rr=None, rf=0.04) -> Assumptions:
    if phases is None:
        phases = [GrowthPhase(name="hg", years=5, growth_rate=0.06, reinvestment_rate=0.4)]
    return Assumptions(
        marginal_tax_rate=tax, risk_free_rate=rf, cost_of_capital=wacc, cost_of_equity=ke,
        cost_of_debt_pretax=kd_pretax, phases=phases, stable_growth_rate=stable_g,
        stable_return_on_capital=stable_roc, stable_reinvestment_rate=stable_rr,
    )


def quarterly_dividends(amount=0.5):
    idx = pd.to_datetime(
        ["2025-03-15", "2025-06-15", "2025-09-15", "2025-12-15"], utc=True
    )
    return pd.Series([amount] * 4, index=idx)


# -- exact reductions ----------------------------------------------------------------
def test_zero_growth_zero_reinvestment_is_a_perpetuity():
    company = make_company(ebit=1000.0, debt=0.0, cash=0.0, shares=100.0)
    a = make_assumptions(wacc=0.10, phases=[], stable_g=0.0, stable_rr=0.0, rf=None)
    result = value_fcff(company, a)
    # NOPAT = 1000 * (1 - 0.25) = 750; firm value = 750 / 0.10 = 7500
    assert result.firm_value == pytest.approx(7500.0)
    assert result.equity_value == pytest.approx(7500.0)
    assert result.value_per_share == pytest.approx(75.0)


def test_cash_and_net_debt_bridge():
    # Same operations, but with debt and cash: equity = firm_value - debt + cash.
    company = make_company(ebit=1000.0, debt=2000.0, cash=500.0, shares=100.0)
    a = make_assumptions(wacc=0.10, phases=[], stable_g=0.0, stable_rr=0.0, rf=None)
    result = value_fcff(company, a)
    assert result.firm_value == pytest.approx(7500.0)
    assert result.equity_value == pytest.approx(7500.0 - 2000.0 + 500.0)


# -- the headline invariant: unlevered FCFF == FCFE ----------------------------------
def test_unlevered_fcff_equals_fcfe():
    company = make_company(ebit=1000.0, debt=0.0, cash=0.0, shares=100.0)
    a = make_assumptions(wacc=0.09, ke=0.09, kd_pretax=0.0, stable_roc=0.09)
    fcff = value_fcff(company, a)
    fcfe = value_fcfe(company, a)
    assert fcff.value_per_share == pytest.approx(fcfe.value_per_share, rel=1e-9)


# -- monotonicity properties ---------------------------------------------------------
def test_higher_discount_rate_lowers_value():
    company = make_company()
    low = value_fcff(company, make_assumptions(wacc=0.09, stable_roc=0.09))
    high = value_fcff(company, make_assumptions(wacc=0.11, stable_roc=0.11))
    assert high.value_per_share < low.value_per_share


def test_higher_stable_growth_raises_value():
    company = make_company()
    low = value_fcff(company, make_assumptions(stable_g=0.01, rf=0.04))
    high = value_fcff(company, make_assumptions(stable_g=0.03, rf=0.04))
    assert high.value_per_share > low.value_per_share


# -- stable-phase discipline (reused Phase 2 assertions) -----------------------------
def test_stable_growth_above_riskfree_raises():
    company = make_company()
    with pytest.raises(ValueError):
        value_fcff(company, make_assumptions(stable_g=0.06, rf=0.04, stable_roc=0.10))


def test_underspecified_phase_raises():
    with pytest.raises(ValueError):
        resolve_phase(GrowthPhase(name="bad", years=3))  # no two of g/RR/ROC


# -- terminal-value warning ----------------------------------------------------------
def test_terminal_value_warning_threshold():
    assert terminal_value_warnings(0.80)  # dominates -> warns
    assert not terminal_value_warnings(0.50)


def test_projection_table_has_one_row_per_year():
    company = make_company()
    result = value_fcff(company, make_assumptions(
        phases=[GrowthPhase(name="hg", years=7, growth_rate=0.05, reinvestment_rate=0.3)]
    ))
    assert len(result.projection) == 7
    assert 0.0 < result.terminal_value_share < 1.0


# -- realistic fixtures --------------------------------------------------------------
def test_aapl_fcff_fcfe_converge_and_are_positive(aapl):
    a = baseline_assumptions(aapl)
    fcff = value_fcff(aapl, a)
    fcfe = value_fcfe(aapl, a)
    assert fcff.value_per_share > 0 and fcfe.value_per_share > 0
    divergence = abs(fcff.value_per_share - fcfe.value_per_share) / fcff.value_per_share
    assert divergence < 0.12  # lightly levered -> close convergence


def test_aapl_ddm_is_a_floor_below_fcfe(aapl):
    a = baseline_assumptions(aapl)
    ddm = value_ddm(aapl, a)
    fcfe = value_fcfe(aapl, a)
    # Apple pays out a small fraction of earnings, so DDM << FCFE.
    assert 0 < ddm.value_per_share < fcfe.value_per_share


def test_ko_dividend_discount_model(ko):
    result = value_ddm(ko, baseline_assumptions(ko))
    assert result.value_per_share > 0
    assert result.engine == "DDM"


def test_ddm_without_dividends_raises():
    company = make_company(dividends=None)
    with pytest.raises(ValueError):
        value_ddm(company, make_assumptions())


def test_ddm_on_synthetic_dividends():
    company = make_company(dividends=quarterly_dividends(0.5), shares=100.0)
    result = value_ddm(company, make_assumptions(ke=0.09, stable_roc=0.09))
    assert result.value_per_share > 0  # trailing DPS = 2.0
