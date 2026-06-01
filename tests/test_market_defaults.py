"""Provenance + staleness behaviour for dated config defaults."""
from __future__ import annotations

from datetime import date

from valuation_engine import config
from valuation_engine.config.market import (
    EQUITY_RISK_PREMIUM,
    RISK_FREE_RATE,
    SourcedDefault,
    market_staleness_warnings,
)
from valuation_engine.config.provenance import Provenance


def test_defaults_carry_source_and_url():
    assert RISK_FREE_RATE.source_url.startswith("https://fred")
    assert "damodaran" in EQUITY_RISK_PREMIUM.source.lower()
    assert RISK_FREE_RATE.value > 0 and EQUITY_RISK_PREMIUM.value > 0


def test_provenance_fresh_vs_stale():
    p = Provenance(as_of=date(2026, 1, 1), source="X", source_url="u", max_age_days=30)
    assert not p.is_stale(today=date(2026, 1, 20))  # 19 days
    assert p.is_stale(today=date(2026, 3, 1))  # 59 days
    assert p.staleness_warning("rf", today=date(2026, 1, 20)) is None
    assert p.staleness_warning("rf", today=date(2026, 3, 1)).startswith("STALE")


def test_sourced_default_warning_names_value_and_source():
    d = SourcedDefault(0.05, Provenance(date(2026, 1, 1), "Damodaran", "http://x", 30))
    warning = d.staleness_warning("equity_risk_premium", today=date(2026, 5, 31))
    assert "STALE" in warning
    assert "equity_risk_premium" in warning
    assert "Damodaran" in warning and "0.05" in warning


def test_market_staleness_collects_old_defaults():
    # 2026-07-01 is >30d after rf (2026-05-15) and erp (2026-01-01); tax (365d window) is fresh.
    warnings = market_staleness_warnings(today=date(2026, 7, 1))
    assert any("risk_free_rate" in w for w in warnings)
    assert any("equity_risk_premium" in w for w in warnings)
    assert not any("marginal_tax_rate" in w for w in warnings)


def test_config_all_staleness_includes_tables():
    # Far future: even the 400-day table windows are blown.
    warnings = config.all_staleness_warnings(today=date(2028, 1, 1))
    assert any("synthetic_rating_table" in w for w in warnings)
    assert any("sector_unlevered_beta" in w for w in warnings)
    assert len(warnings) >= 4
