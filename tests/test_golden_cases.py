"""Golden-case tests: pin the intrinsic per-share values for known firms.

The baseline assumptions are deterministic (rf/ERP come from fixed config defaults, not
the clock), so these values are reproducible. A change here means the engine math moved —
intentional changes update the goldens, regressions get caught.
"""
from __future__ import annotations

import pytest

from valuation_engine.pipeline import run_valuation

# value per share from the deterministic baseline on the committed fixtures
GOLDEN = {
    "AAPL": {"fcff": 145.09, "fcfe": 150.18},
    "KO": {"fcff": 64.19, "fcfe": 67.93},
}


@pytest.mark.parametrize("ticker", list(GOLDEN))
def test_golden_intrinsic_values(provider, ticker):
    run = run_valuation(ticker, provider, run_monte_carlo=False)
    by_method = {e.method: e.value_per_share for e in run.triangulation.estimates}
    assert by_method["FCFF"] == pytest.approx(GOLDEN[ticker]["fcff"], rel=0.03)
    assert by_method["FCFE"] == pytest.approx(GOLDEN[ticker]["fcfe"], rel=0.03)


@pytest.mark.parametrize("ticker", list(GOLDEN))
def test_pipeline_produces_report_and_margin(provider, ticker):
    run = run_valuation(ticker, provider, run_monte_carlo=False)
    assert "# Valuation report" in run.report_markdown
    assert run.margin_of_safety is not None
    assert run.price and run.price > 0


def test_margin_of_safety_threshold_flag(provider):
    # A deep-discount threshold the conservative AAPL valuation cannot meet (price > value).
    run = run_valuation("AAPL", provider, run_monte_carlo=False, margin_of_safety_threshold=0.20)
    assert run.meets_threshold is False
