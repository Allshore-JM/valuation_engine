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

    def suggest_peers(self, ticker: str, *, max_peers: int = 6) -> list[str]:
        """Comparable tickers from the firm's sector (size-ranked), industry as fallback.

        Uses yfinance's Sector/Industry constituent lists. The sector is preferred because
        Yahoo's industry buckets are often too narrow (e.g. Apple's "consumer-electronics"
        is dominated by Apple plus tiny names). Candidates are ranked by closeness in market
        weight to the target, so they are size-comparable. Returns [] if nothing usable.
        """
        import yfinance as yf

        self._throttle()
        sym = ticker.upper()
        try:
            info = dict(yf.Ticker(ticker).info)
        except Exception:  # noqa: BLE001
            info = {}

        for key, cls in (
            (info.get("sectorKey"), getattr(yf, "Sector", None)),
            (info.get("industryKey"), getattr(yf, "Industry", None)),
        ):
            if not key or cls is None:
                continue
            try:
                df = cls(key).top_companies
            except Exception:  # noqa: BLE001
                continue
            if df is None or not hasattr(df, "index") or len(df) == 0:
                continue
            symbols = [str(s).upper() for s in df.index]
            weights: dict[str, float] = {}
            if "market weight" in getattr(df, "columns", []):
                for s, w in df["market weight"].items():
                    try:
                        weights[str(s).upper()] = float(w)
                    except (TypeError, ValueError):
                        pass
            peers = [s for s in symbols if s != sym]
            if weights and sym in weights:  # rank by closeness in size to the target
                target_weight = weights[sym]
                peers.sort(key=lambda s: abs(weights.get(s, 0.0) - target_weight))
            if peers:
                return peers[:max_peers]
        return []

    def search(self, query: str, *, max_results: int = 8) -> list[tuple[str, str]]:
        """Search companies/tickers by name or symbol -> [(symbol, 'SYM — Name (Exchange)')].

        Backed by yfinance's Yahoo search. Equities only, de-duplicated. Returns [] on a
        too-short query or any failure.
        """
        query = (query or "").strip()
        if len(query) < 2:
            return []
        try:
            import yfinance as yf

            quotes = yf.Search(query).quotes
        except Exception:  # noqa: BLE001
            return []
        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        for q in quotes:
            if q.get("quoteType") != "EQUITY":
                continue
            symbol = q.get("symbol")
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            name = q.get("shortname") or q.get("longname") or ""
            exch = q.get("exchDisp") or ""
            label = f"{symbol} — {name}" + (f" ({exch})" if exch else "")
            out.append((symbol, label))
            if len(out) >= max_results:
                break
        return out

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
