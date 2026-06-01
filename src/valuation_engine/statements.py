"""Small statement-reading helpers shared by the input, engine, and relative layers.

Kept provider-agnostic and dependency-light (pandas only) so both ``inputs`` and
``engines`` can use them without an import cycle.
"""
from __future__ import annotations

import pandas as pd


def latest_valid(statement: pd.DataFrame | None, label: str) -> float | None:
    """Most recent NON-null value for a canonical row.

    yfinance leaves NaNs in the latest column for some lines, so a blind ``.iloc[0]``
    is unsafe — take the most recent column that actually has a value.
    """
    if statement is None or label not in getattr(statement, "index", []):
        return None
    series = statement.loc[label].dropna()
    return float(series.iloc[0]) if len(series) else None


def historical_growth(statement: pd.DataFrame | None, label: str) -> float | None:
    """CAGR of a line item across the available (non-null) history, or None.

    Columns are most-recent-first, so the oldest value is last. Returns None unless both
    endpoints are positive (a CAGR through zero/negatives is meaningless).
    """
    if statement is None or label not in getattr(statement, "index", []):
        return None
    series = statement.loc[label].dropna()
    if len(series) < 2:
        return None
    latest, oldest = float(series.iloc[0]), float(series.iloc[-1])
    years = len(series) - 1
    if latest > 0 and oldest > 0 and years > 0:
        return (latest / oldest) ** (1.0 / years) - 1.0
    return None
