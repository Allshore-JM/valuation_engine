"""Invariants that must hold across firms (framework §7)."""
from __future__ import annotations

import pytest

from valuation_engine.engines import baseline_assumptions, value_fcfe, value_fcff
from valuation_engine.reconcile.perturb import with_updates

FIRMS = ["AAPL", "KO"]


@pytest.mark.parametrize("ticker", FIRMS)
def test_stable_growth_not_above_risk_free(provider, ticker):
    a = baseline_assumptions(provider.get_company(ticker))
    assert a.stable_growth_rate <= a.risk_free_rate + 1e-9


@pytest.mark.parametrize("ticker", FIRMS)
def test_tax_rate_in_range(provider, ticker):
    a = baseline_assumptions(provider.get_company(ticker))
    assert 0.0 <= a.marginal_tax_rate < 1.0


@pytest.mark.parametrize("ticker", FIRMS)
def test_per_share_positive_and_fcff_fcfe_converge(provider, ticker):
    company = provider.get_company(ticker)
    a = baseline_assumptions(company)
    fcff = value_fcff(company, a).value_per_share
    fcfe = value_fcfe(company, a).value_per_share
    assert fcff > 0 and fcfe > 0  # per-share value non-negative for healthy firms
    assert abs(fcff - fcfe) / fcff < 0.15  # the two intrinsic methods agree


@pytest.mark.parametrize("ticker", FIRMS)
def test_terminal_value_share_is_a_fraction(provider, ticker):
    company = provider.get_company(ticker)
    result = value_fcff(company, baseline_assumptions(company))
    assert 0.0 < result.terminal_value_share < 1.0


@pytest.mark.parametrize("ticker", FIRMS)
def test_higher_wacc_lowers_value(provider, ticker):
    company = provider.get_company(ticker)
    a = baseline_assumptions(company)
    base = value_fcff(company, a).value_per_share
    higher = value_fcff(company, with_updates(a, cost_of_capital=a.cost_of_capital + 0.02)).value_per_share
    assert higher < base
