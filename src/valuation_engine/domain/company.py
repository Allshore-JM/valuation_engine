"""The top-level object a valuation engine consumes."""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from valuation_engine.domain.financials import Financials


class Company(BaseModel):
    """A company plus the market + statement data needed to value it.

    Populated by a `DataProvider`. Every market field is optional: providers
    (especially yfinance's ``.info``) drop fields without warning, so the engines must
    fall back to computing from statements rather than assuming a key exists.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Identity / classification
    ticker: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None

    # Market data (snapshot)
    price: float | None = None
    shares_outstanding: float | None = None
    market_cap: float | None = None
    beta: float | None = None

    # Balance-sheet snapshot used for the firm -> equity bridge
    total_debt: float | None = None
    cash_and_equivalents: float | None = None
    minority_interest: float | None = None

    # Distributions: historical dividends per share, indexed by date.
    dividends: pd.Series | None = None

    # Historical statements.
    financials: Financials | None = None

    # Relative-valuation universe (peer tickers).
    peers: list[str] = Field(default_factory=list)

    # Data-quality / special-case flags raised by the data layer (negative book equity,
    # negative EBITDA, financial-service firm, young firm, ...). Phase 7 routes these
    # away from the default pipeline; until then they are surfaced as warnings.
    data_warnings: list[str] = Field(default_factory=list)
