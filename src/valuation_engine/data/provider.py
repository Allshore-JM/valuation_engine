"""The single interface every data source implements.

Keeping all data access behind this protocol means a new feed (yfinance, SEC EDGAR, or
a paid provider) drops in by writing one class — no engine changes. The concrete
``YFinanceProvider`` arrives in Phase 1.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from valuation_engine.domain import Company, Financials


@runtime_checkable
class DataProvider(Protocol):
    """Fetch typed domain objects for a ticker (and its peers).

    Implementations must:
      * treat every upstream field as optional, falling back to statement-derived
        values rather than assuming a key exists;
      * cache fetched data and rate-limit politely;
      * normalize source labels onto the canonical ``Financials`` row labels in one
        isolated place;
      * support pinning any input to a manual value via ``manual_override``.
    """

    def get_company(self, ticker: str) -> Company:
        """Return a fully populated Company (market data + ``.financials``)."""
        ...

    def get_financials(self, ticker: str) -> Financials:
        """Return just the normalized historical statements for ``ticker``."""
        ...

    def get_peers(self, tickers: list[str]) -> list[Company]:
        """Return Companies for a list of peer tickers (for the relative engine)."""
        ...

    def manual_override(self, field: str, value: object) -> None:
        """Pin ``field`` to ``value``, overriding whatever the source returns."""
        ...
