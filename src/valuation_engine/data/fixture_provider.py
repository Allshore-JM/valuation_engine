"""FixtureProvider — offline DataProvider that replays a committed RawSnapshot.

This is the deterministic input for the whole test suite (and for demos without
network). It runs the SAME normalization path as ``YFinanceProvider``, so tests exercise
the real source -> canonical mapping logic — only the fetch is replaced by reading a JSON
file from ``data/fixtures/``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from valuation_engine.data import normalize
from valuation_engine.data.snapshot import RawSnapshot
from valuation_engine.domain import Company, Financials

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class FixtureProvider:
    """Satisfies the ``DataProvider`` protocol from committed snapshots."""

    def __init__(self, fixtures_dir: str | Path = DEFAULT_FIXTURES_DIR) -> None:
        self.fixtures_dir = Path(fixtures_dir)
        self._overrides: dict[str, Any] = {}

    def _snapshot(self, ticker: str) -> RawSnapshot:
        path = self.fixtures_dir / f"{ticker.upper()}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"No fixture for {ticker!r} at {path}. Available: {self.available()}"
            )
        return RawSnapshot.from_json(path.read_text(encoding="utf-8"))

    def get_company(self, ticker: str) -> Company:
        return normalize.to_company(self._snapshot(ticker), self._overrides)

    def get_financials(self, ticker: str) -> Financials:
        return normalize.to_financials(self._snapshot(ticker))

    def get_peers(self, tickers: list[str]) -> list[Company]:
        return [self.get_company(t) for t in tickers]

    def manual_override(self, field: str, value: object) -> None:
        self._overrides[field] = value

    def available(self) -> list[str]:
        return sorted(p.stem for p in self.fixtures_dir.glob("*.json"))
