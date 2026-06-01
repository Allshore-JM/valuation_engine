"""Phase 4 relative-valuation tests: regression recovery, multiples, four-step on fixtures."""
from __future__ import annotations

import pytest

from valuation_engine.domain import Company
from valuation_engine.engines.relative import (
    _apply_multiple,
    describe,
    linear_regression,
    relative_valuation,
    relative_value,
)
from valuation_engine.inputs import compute_multiples

TECH_PEERS = ["MSFT", "NVDA", "ORCL", "CRM", "AVGO"]
BEVERAGE_PEERS = ["PEP", "MNST", "KDP", "STZ"]


# -- pure mechanics (deterministic) --------------------------------------------------
def test_linear_regression_recovers_known_coefficients():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [3.0 * x + 7.0 for x in xs]  # slope 3, intercept 7, perfect fit
    reg = linear_regression(xs, ys, driver="growth")
    assert reg.slope == pytest.approx(3.0)
    assert reg.intercept == pytest.approx(7.0)
    assert reg.r_squared == pytest.approx(1.0)
    assert reg.predict(10.0) == pytest.approx(37.0)


def test_describe_distribution():
    stat = describe([10.0, 12.0, 14.0, 16.0, 100.0])
    assert stat.n == 5
    assert stat.median == pytest.approx(14.0)
    assert stat.minimum == 10.0 and stat.maximum == 100.0


def test_apply_multiple_equity_and_enterprise_bridge():
    company = Company(ticker="T", shares_outstanding=100.0, total_debt=50.0,
                      cash_and_equivalents=30.0)
    # Equity multiple: value = multiple * metric, per share = /shares.
    assert _apply_multiple(15.0, 1000.0, "equity", company) == pytest.approx(150.0)
    # Enterprise multiple: EV = multiple * metric, then EV - debt + cash -> equity.
    # 10 * 200 = 2000 EV; equity = 2000 - 50 + 30 = 1980; /100 = 19.8
    assert _apply_multiple(10.0, 200.0, "enterprise", company) == pytest.approx(19.8)


# -- multiples on a real fixture -----------------------------------------------------
def test_compute_multiples_aapl(aapl):
    m = compute_multiples(aapl)
    assert m.pe and m.pe > 0
    assert m.ev_ebitda and m.ev_ebitda > 0
    assert m.ev_sales and m.ev_sales > 0
    assert m.pb and m.pb > 0
    assert m.enterprise_value and m.enterprise_value > 0
    assert m.operating_margin and m.operating_margin > 0


# -- four-step process on peer sets --------------------------------------------------
def test_relative_value_pe_against_tech_peers(provider, aapl):
    peers = provider.get_peers(TECH_PEERS)
    rv = relative_value(aapl, peers, "pe")
    assert rv.distribution is not None and rv.distribution.n == len(TECH_PEERS)
    assert rv.median_multiple and rv.median_multiple > 0
    assert rv.implied_value_per_share_median and rv.implied_value_per_share_median > 0
    assert rv.basis == "equity" and rv.driver == "earnings_growth"


def test_relative_value_enterprise_multiple(provider, aapl):
    peers = provider.get_peers(TECH_PEERS)
    rv = relative_value(aapl, peers, "ev_ebitda")
    assert rv.basis == "enterprise"
    assert rv.implied_value_per_share_median and rv.implied_value_per_share_median > 0


def test_relative_valuation_runs_all_multiples_and_regresses(provider, aapl):
    peers = provider.get_peers(TECH_PEERS)
    results = relative_valuation(aapl, peers)
    assert set(results) == {"pe", "pb", "ev_ebitda", "ev_sales"}
    for rv in results.values():
        assert rv.distribution is not None
        assert rv.implied_value_per_share_median and rv.implied_value_per_share_median > 0
    # the regression step is exercised on at least one multiple (peers have spread)
    assert any(rv.regression is not None for rv in results.values())


def test_relative_value_ko_against_beverage_peers(provider, ko):
    peers = provider.get_peers(BEVERAGE_PEERS)
    rv = relative_value(ko, peers, "pe")
    assert rv.implied_value_per_share_median and rv.implied_value_per_share_median > 0
    assert rv.distribution.n == len(BEVERAGE_PEERS)


def test_insufficient_peers_falls_back_to_median(provider, aapl):
    one_peer = provider.get_peers(["MSFT"])
    rv = relative_value(aapl, one_peer, "pe", min_peers=3)
    assert rv.regression is None
    assert rv.median_multiple is not None  # median still works with one peer
    assert any("insufficient" in w for w in rv.warnings)


def test_unknown_multiple_raises(aapl):
    with pytest.raises(ValueError):
        relative_value(aapl, [], "price_to_dreams")
