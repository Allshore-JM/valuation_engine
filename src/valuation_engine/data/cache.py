"""Disk cache for RawSnapshots, keyed by ticker, with a freshness window.

Deliberately a tiny JSON-file cache rather than ``requests-cache``: yfinance 1.x fetches
through ``curl_cffi``, which ``requests-cache`` does not wrap cleanly. Snapshots are the
natural cache unit anyway (one file per ticker), and the committed fixtures share the
exact same format.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from valuation_engine.data.snapshot import RawSnapshot


class SnapshotCache:
    def __init__(self, cache_dir: str | Path, max_age_days: int = 1) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_days = max_age_days

    def _path(self, ticker: str) -> Path:
        return self.cache_dir / f"{ticker.upper()}.json"

    def get(self, ticker: str) -> RawSnapshot | None:
        path = self._path(ticker)
        if not path.exists():
            return None
        snap = RawSnapshot.from_json(path.read_text(encoding="utf-8"))
        return None if self._is_stale(snap) else snap

    def put(self, snapshot: RawSnapshot) -> Path:
        path = self._path(snapshot.ticker)
        path.write_text(snapshot.to_json(), encoding="utf-8")
        return path

    def _is_stale(self, snap: RawSnapshot) -> bool:
        try:
            recorded = _dt.date.fromisoformat(snap.recorded_at)
        except ValueError:
            return True
        return (_dt.date.today() - recorded).days > self.max_age_days
