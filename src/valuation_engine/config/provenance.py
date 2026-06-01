"""Provenance + staleness for config defaults.

Market inputs (risk-free rate, ERP) and Damodaran's annual tables drift. Each default
carries the date it was set and where to refresh it, and reports when it has gone stale
so the report / CLI can warn the user — transparency over a falsely precise number.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Provenance:
    """When a default was set, where it came from, and how long it stays fresh."""

    as_of: date
    source: str
    source_url: str
    max_age_days: int = 30
    note: str = ""

    def age_days(self, today: date | None = None) -> int:
        return ((today or date.today()) - self.as_of).days

    def is_stale(self, today: date | None = None) -> bool:
        return self.age_days(today) > self.max_age_days

    def staleness_warning(self, label: str, today: date | None = None) -> str | None:
        """A one-line refresh nudge if stale, else None."""
        if not self.is_stale(today):
            return None
        return (
            f"STALE: {label} was set {self.as_of.isoformat()} "
            f"({self.age_days(today)}d ago, max {self.max_age_days}d). "
            f"Refresh from {self.source}: {self.source_url}"
        )
