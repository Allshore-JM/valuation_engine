"""Reference tables, dated market defaults, and a staleness collector.

Kept separate from logic so every number the engine leans on is easy to audit and
refresh. ``all_staleness_warnings`` is what the report / CLI calls to nudge the user
when a default has aged out.
"""
from __future__ import annotations

from datetime import date

from valuation_engine.config import defaults, market
from valuation_engine.config.market import SourcedDefault, market_staleness_warnings
from valuation_engine.config.provenance import Provenance


def all_staleness_warnings(today: date | None = None) -> list[str]:
    """Collect refresh nudges across market defaults and the Damodaran tables."""
    warnings = list(market_staleness_warnings(today))
    for label, prov in (
        ("synthetic_rating_table", defaults.SYNTHETIC_RATING_TABLE_PROVENANCE),
        ("sector_unlevered_beta", defaults.SECTOR_UNLEVERED_BETA_PROVENANCE),
    ):
        warning = prov.staleness_warning(label, today)
        if warning:
            warnings.append(warning)
    return warnings


__all__ = [
    "defaults",
    "market",
    "Provenance",
    "SourcedDefault",
    "market_staleness_warnings",
    "all_staleness_warnings",
]
