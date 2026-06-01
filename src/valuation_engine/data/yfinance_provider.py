"""YFinanceProvider — concrete DataProvider backed by the (pinned) yfinance library.

yfinance is an unofficial Yahoo scraper and can break without warning, so:
  * fetched snapshots are cached on disk (``SnapshotCache``);
  * live calls are throttled (polite rate limiting);
  * the test suite never calls this class live — it replays committed fixtures via
    ``FixtureProvider``. One ``@integration`` test exercises the live path on demand.

``import yfinance`` is deferred to the moment of fetch so that importing this module
(and the package) stays cheap and offline.
"""
from __future__ import annotations

import datetime as _dt
import time
from pathlib import Path
from typing import Any

import pandas as pd

from valuation_engine.data import normalize
from valuation_engine.data.cache import SnapshotCache
from valuation_engine.data.snapshot import (
    INFO_KEYS,
    STATEMENT_KEYS,
    RawSnapshot,
    df_to_jsonable,
    series_to_jsonable,
    to_native,
)
from valuation_engine.domain import Company, Financials

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "valuation_engine"


class YFinanceProvider:
    """Satisfies the ``DataProvider`` protocol using yfinance."""

    def __init__(
        self,
        cache_dir: str | Path = DEFAULT_CACHE_DIR,
        max_age_days: int = 1,
        min_request_interval: float = 1.5,
    ) -> None:
        self._cache = SnapshotCache(cache_dir, max_age_days=max_age_days)
        self._min_interval = min_request_interval
        self._last_call = 0.0
        self._overrides: dict[str, Any] = {}

    # -- DataProvider interface ------------------------------------------------------
    def get_company(self, ticker: str) -> Company:
        return normalize.to_company(self._snapshot(ticker), self._overrides)

    def get_financials(self, ticker: str) -> Financials:
        return normalize.to_financials(self._snapshot(ticker))

    def get_peers(self, tickers: list[str]) -> list[Company]:
        return [self.get_company(t) for t in tickers]

    def manual_override(self, field: str, value: object) -> None:
        self._overrides[field] = value

    # -- snapshot plumbing -----------------------------------------------------------
    def _snapshot(self, ticker: str) -> RawSnapshot:
        cached = self._cache.get(ticker)
        if cached is not None:
            return cached
        snap = self._fetch(ticker)
        self._cache.put(snap)
        return snap

    def snapshot_for(self, ticker: str) -> RawSnapshot:
        """Force a live fetch and return the snapshot (used to record fixtures)."""
        return self._fetch(ticker)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def _fetch(self, ticker: str) -> RawSnapshot:
        import yfinance as yf

        self._throttle()
        t = yf.Ticker(ticker)

        statements: dict[str, Any] = {}
        for key in STATEMENT_KEYS:
            try:
                df = getattr(t, key)
            except Exception:  # noqa: BLE001 - yfinance raises many shapes
                df = None
            statements[key] = df_to_jsonable(df if isinstance(df, pd.DataFrame) else None)

        try:
            raw_info = dict(t.info)
        except Exception:  # noqa: BLE001
            raw_info = {}
        info = {
            k: to_native(raw_info.get(k))
            for k in INFO_KEYS
            if raw_info.get(k) is not None
        }

        try:
            fast = {k: to_native(t.fast_info[k]) for k in t.fast_info.keys()}
        except Exception:  # noqa: BLE001
            fast = {}

        try:
            dividends = series_to_jsonable(t.dividends)
        except Exception:  # noqa: BLE001
            dividends = None

        return RawSnapshot(
            ticker=ticker.upper(),
            recorded_at=_dt.date.today().isoformat(),
            source="yfinance",
            info=info,
            fast_info=fast,
            dividends=dividends,
            statements=statements,
        )
