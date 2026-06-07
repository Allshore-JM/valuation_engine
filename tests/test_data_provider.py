"""Phase 1 data-layer tests — all offline against committed fixtures.

The only network-touching test is marked @integration and skipped by default.
"""
from __future__ import annotations

import pandas as pd
import pytest

from valuation_engine.data import DataProvider, FixtureProvider, YFinanceProvider


def test_providers_satisfy_protocol(tmp_path):
    assert isinstance(FixtureProvider(), DataProvider)
    assert isinstance(YFinanceProvider(cache_dir=tmp_path), DataProvider)


def test_available_fixtures():
    assert set(FixtureProvider().available()) >= {"AAPL", "KO"}


def test_company_core_fields(aapl):
    assert aapl.ticker == "AAPL"
    assert aapl.name and "Apple" in aapl.name
    assert aapl.sector == "Technology"
    assert aapl.currency == "USD"
    assert aapl.price and aapl.price > 0
    assert aapl.shares_outstanding and aapl.shares_outstanding > 1e9
    assert aapl.beta is not None
    assert aapl.total_debt and aapl.total_debt > 0
    assert aapl.cash_and_equivalents and aapl.cash_and_equivalents > 0
    assert aapl.market_cap and aapl.market_cap > 0


def test_canonical_statements_present(aapl):
    fin = aapl.financials
    assert fin is not None
    assert fin.currency == "USD"
    for label in ("TotalRevenue", "EBIT", "EBITDA", "NetIncome", "InterestExpense", "DilutedShares"):
        assert label in fin.income_statement.index, label
    for label in ("TotalAssets", "TotalDebt", "CommonStockEquity", "InvestedCapital"):
        assert label in fin.balance_sheet.index, label
    for label in ("OperatingCashFlow", "CapitalExpenditure", "Depreciation", "FreeCashFlow"):
        assert label in fin.cash_flow.index, label


def test_statement_columns_are_descending_dates(aapl):
    cols = list(aapl.financials.income_statement.columns)
    assert all(isinstance(c, pd.Timestamp) for c in cols)
    assert cols == sorted(cols, reverse=True)  # most-recent period first
    assert len(cols) >= 4  # >= 4-5 years of annual history


def test_quarterly_statements_present_for_ttm(aapl):
    # Phase 2 builds trailing-twelve-month figures from these.
    assert aapl.financials.income_statement_quarterly is not None
    assert "TotalRevenue" in aapl.financials.income_statement_quarterly.index


def test_statement_values_sane(aapl):
    inc = aapl.financials.income_statement
    revenue = inc.loc["TotalRevenue"].iloc[0]
    net_income = inc.loc["NetIncome"].iloc[0]
    assert revenue > net_income > 0  # revenue exceeds positive net income


def test_dividends_series(aapl):
    assert isinstance(aapl.dividends, pd.Series)
    assert len(aapl.dividends) > 0


def test_optional_fields_differ_across_firms(aapl, ko):
    # KO reports a noncontrolling (minority) interest; AAPL does not. Optionality must
    # be represented faithfully, not invented.
    assert ko.minority_interest is not None and ko.minority_interest > 0
    assert aapl.minority_interest is None
    # KO reports no separate R&D line; AAPL does.
    assert "ResearchAndDevelopment" not in ko.financials.income_statement.index
    assert "ResearchAndDevelopment" in aapl.financials.income_statement.index


def test_ko_is_dividend_payer(ko):
    assert ko.name and "Coca-Cola" in ko.name
    assert ko.dividends is not None and len(ko.dividends) > 0
    assert ko.sector == "Consumer Defensive"


def test_healthy_firms_have_no_special_case_warnings(aapl, ko):
    for company in (aapl, ko):
        joined = " ".join(company.data_warnings).lower()
        assert "negative" not in joined
        assert "financial-service" not in joined
        assert "missing" not in joined


def test_manual_override_pins_value_and_is_audited():
    prov = FixtureProvider()
    prov.manual_override("beta", 0.9)
    company = prov.get_company("AAPL")
    assert company.beta == 0.9
    assert any("override applied: beta" in w for w in company.data_warnings)


def test_missing_fixture_raises():
    with pytest.raises(FileNotFoundError):
        FixtureProvider().get_company("NOPE")


def test_suggest_peers_offline(provider):
    peers = provider.suggest_peers("AAPL")
    assert "MSFT" in peers and "AAPL" not in peers
    assert all((provider.fixtures_dir / f"{p}.json").exists() for p in peers)
    assert provider.suggest_peers("UNKNOWN_TICKER") == []


@pytest.mark.integration
def test_live_suggest_peers(tmp_path):
    peers = YFinanceProvider(cache_dir=tmp_path).suggest_peers("AAPL")
    assert peers and "AAPL" not in peers  # non-empty, never includes the target itself


@pytest.mark.integration
def test_live_yfinance_fetch_smoke(tmp_path):
    """Live network smoke test. Run with: pytest -m integration."""
    company = YFinanceProvider(cache_dir=tmp_path).get_company("MSFT")
    assert company.ticker == "MSFT"
    assert company.price and company.price > 0
    assert company.financials.income_statement is not None
