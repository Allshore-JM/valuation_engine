"""Live market-data helpers: pure ERP formula (offline) + gated live fetch/search."""
from __future__ import annotations

import pytest

from valuation_engine.data import YFinanceProvider
from valuation_engine.inputs.market_data import (
    EXPECTED_MARKET_RETURN,
    ERP_CEILING,
    ERP_FLOOR,
    live_equity_risk_premium,
    live_risk_free_rate,
)


def test_live_erp_formula_and_clamp():
    # ERP = expected market return - rf, clamped to [floor, ceiling].
    assert live_equity_risk_premium(0.045) == pytest.approx(EXPECTED_MARKET_RETURN.value - 0.045)
    assert live_equity_risk_premium(0.005) == ERP_CEILING  # 0.079 -> ceiling
    assert live_equity_risk_premium(0.075) == ERP_FLOOR    # 0.0091 -> floor


@pytest.mark.integration
def test_live_risk_free_rate_is_sane():
    rf = live_risk_free_rate()
    assert rf is None or 0.0 < rf < 0.15


@pytest.mark.integration
def test_yfinance_ticker_search():
    results = YFinanceProvider().search("apple")
    assert any(sym == "AAPL" for sym, _label in results)
    assert all(len(item) == 2 for item in results)  # (symbol, label) tuples
