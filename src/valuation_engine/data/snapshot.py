"""Raw provider snapshot: the on-disk format shared by the cache and the test fixtures.

A ``RawSnapshot`` is a faithful, JSON-serializable recording of what a provider returned
for one ticker *before* normalization. The disk cache stores them keyed by ticker; the
committed test fixtures are hand-picked snapshots. ``normalize.py`` turns a snapshot into
the typed ``Company`` / ``Financials`` the engines consume — that is the single place the
source -> canonical label mapping lives, so a new provider just has to emit a snapshot of
this shape.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

# Curated subset of yfinance ``.info`` worth recording (identity, market snapshot, and
# the ratios the relative engine will want). Keeps fixtures lean and stable; volatile or
# bulky fields (officers, long business summary) are dropped.
INFO_KEYS: tuple[str, ...] = (
    "longName", "shortName", "sector", "industry", "country",
    "currency", "financialCurrency",
    "sharesOutstanding", "impliedSharesOutstanding", "floatShares",
    "marketCap", "enterpriseValue", "beta",
    "currentPrice", "regularMarketPrice", "previousClose",
    "totalDebt", "totalCash",
    "bookValue", "priceToBook", "trailingPE", "forwardPE", "trailingEps",
    "ebitda", "enterpriseToEbitda", "enterpriseToRevenue",
    "profitMargins", "operatingMargins", "returnOnEquity", "returnOnAssets",
    "dividendRate", "dividendYield", "payoutRatio",
    "revenueGrowth", "earningsGrowth",
)

# The six statement accessors pulled from a yfinance Ticker.
STATEMENT_KEYS: tuple[str, ...] = (
    "income_stmt", "balance_sheet", "cashflow",
    "quarterly_income_stmt", "quarterly_balance_sheet", "quarterly_cashflow",
)


def to_native(v: Any) -> Any:
    """Coerce a scalar to a JSON-native type (preserving bool/str, numbers as float)."""
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


def _cell(v: Any) -> Any:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    return str(v)


def df_to_jsonable(df: pd.DataFrame | None) -> dict | None:
    """Serialize a statement DataFrame (date columns, label index) to plain JSON."""
    if df is None or getattr(df, "empty", True):
        return None
    columns = [c.isoformat() if hasattr(c, "isoformat") else str(c) for c in df.columns]
    index = [str(i) for i in df.index]
    data = [[_cell(v) for v in row] for row in df.to_numpy()]
    return {"columns": columns, "index": index, "data": data}


def df_from_jsonable(obj: dict | None) -> pd.DataFrame | None:
    if not obj:
        return None
    columns = [pd.Timestamp(c) for c in obj["columns"]]
    return pd.DataFrame(obj["data"], index=obj["index"], columns=columns, dtype="float64")


def series_to_jsonable(s: pd.Series | None) -> dict | None:
    if s is None or len(s) == 0:
        return None
    index = [x.isoformat() if hasattr(x, "isoformat") else str(x) for x in s.index]
    values = [_cell(v) for v in s.to_numpy()]
    return {"index": index, "values": values}


def series_from_jsonable(obj: dict | None) -> pd.Series | None:
    if not obj:
        return None
    index = pd.to_datetime(obj["index"], utc=True, errors="coerce")
    return pd.Series(obj["values"], index=index, dtype="float64")


class RawSnapshot(BaseModel):
    """A JSON-native recording of one provider fetch for one ticker."""

    ticker: str
    recorded_at: str  # ISO date, e.g. "2026-05-31" — provenance + cache-freshness key
    source: str = "yfinance"
    info: dict[str, Any] = Field(default_factory=dict)
    fast_info: dict[str, Any] = Field(default_factory=dict)
    dividends: dict[str, Any] | None = None
    statements: dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, text: str) -> "RawSnapshot":
        return cls.model_validate_json(text)
