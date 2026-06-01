"""Hardcoded reference tables (Damodaran), each stamped with provenance.

Kept in one place so the numbers are easy to audit and refresh. Scalar market defaults
(risk-free rate, ERP, tax) live in ``market.py``; this module holds the lookup tables.
"""
from __future__ import annotations

import math
from datetime import date

from valuation_engine.config.provenance import Provenance

# Interest-coverage ratio -> synthetic credit rating -> default spread (decimal).
# Large-cap (> $5B) table; each row covers coverage in [low, high).
SYNTHETIC_RATING_TABLE: list[tuple[float, float, str, float]] = [
    (8.50, math.inf, "Aaa/AAA", 0.0059),
    (6.50, 8.50, "Aa2/AA", 0.0078),
    (5.50, 6.50, "A1/A+", 0.0098),
    (4.25, 5.50, "A2/A", 0.0108),
    (3.00, 4.25, "A3/A-", 0.0122),
    (2.50, 3.00, "Baa2/BBB", 0.0156),
    (2.25, 2.50, "Ba1/BB+", 0.0200),
    (2.00, 2.25, "Ba2/BB", 0.0240),
    (1.75, 2.00, "B1/B+", 0.0351),
    (1.50, 1.75, "B2/B", 0.0421),
    (1.25, 1.50, "B3/B-", 0.0515),
    (0.80, 1.25, "Caa/CCC", 0.0820),
    (0.65, 0.80, "Ca2/CC", 0.0864),
    (0.20, 0.65, "C2/C", 0.1134),
    (-math.inf, 0.20, "D2/D", 0.1512),
]
SYNTHETIC_RATING_TABLE_PROVENANCE = Provenance(
    as_of=date(2026, 1, 1),
    source="Damodaran 'Ratings, Interest Coverage Ratios and Default Spreads' (large cap)",
    source_url="https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html",
    max_age_days=400,
    note="Spreads shift yearly; small/risky firms use a different coverage banding.",
)

# Broad sector -> average UNLEVERED ("asset") beta, keyed to yfinance sector names so it
# matches Company.sector directly. A pragmatic coarsening of Damodaran's industry betas.
SECTOR_UNLEVERED_BETA: dict[str, float] = {
    "Technology": 1.15,
    "Communication Services": 0.95,
    "Consumer Cyclical": 1.05,
    "Consumer Defensive": 0.55,
    "Energy": 0.95,
    "Financial Services": 0.90,
    "Healthcare": 0.95,
    "Industrials": 1.00,
    "Basic Materials": 0.95,
    "Real Estate": 0.65,
    "Utilities": 0.40,
}
SECTOR_UNLEVERED_BETA_PROVENANCE = Provenance(
    as_of=date(2026, 1, 1),
    source="Damodaran 'Levered and Unlevered Betas by Industry' (US), sector-averaged",
    source_url="https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html",
    max_age_days=400,
    note="Broad-sector approximation; for precision map to Damodaran's 90+ industries.",
)

# Default projection shape when the caller does not specify phases:
# (high-growth years, transition years). The stable phase is an open-ended perpetuity.
DEFAULT_PHASE_YEARS: tuple[int, int] = (5, 5)
