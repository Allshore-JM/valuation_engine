"""Market-level default inputs, each stamped with provenance + a refresh source.

These are *starting placeholders*, not live data. Override them per valuation, and when
you refresh the stored value, update its ``as_of`` date too. The engine surfaces a
staleness warning when a default is older than its ``max_age_days``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from valuation_engine.config.provenance import Provenance


@dataclass(frozen=True)
class SourcedDefault:
    """A scalar default bundled with its provenance."""

    value: float
    provenance: Provenance

    @property
    def as_of(self) -> date:
        return self.provenance.as_of

    @property
    def source(self) -> str:
        return self.provenance.source

    @property
    def source_url(self) -> str:
        return self.provenance.source_url

    def staleness_warning(self, label: str, today: date | None = None) -> str | None:
        return self.provenance.staleness_warning(f"{label} (={self.value:g})", today)


# Long-term government bond yield in the cash-flow currency (US 10y Treasury here).
RISK_FREE_RATE = SourcedDefault(
    value=0.043,
    provenance=Provenance(
        as_of=date(2026, 5, 15),
        source="FRED series DGS10 (10-Year Treasury Constant Maturity)",
        source_url="https://fred.stlouisfed.org/series/DGS10",
        max_age_days=30,
        note="Placeholder; use the long-term govt bond yield in the cash-flow currency.",
    ),
)

# Implied equity risk premium for the US market (S&P 500).
# Damodaran's start-of-2026 implied ERP = 4.23% (S&P 500 at 6845.5), ~ the 1960-2025 average.
EQUITY_RISK_PREMIUM = SourcedDefault(
    value=0.0423,
    provenance=Provenance(
        as_of=date(2026, 1, 1),
        source="Damodaran implied US equity risk premium (start-of-2026 = 4.23%)",
        source_url="https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histimpl.html",
        max_age_days=30,
        note=(
            "Maintained annual series (histimpl.html / histimpl.xls). Damodaran also posts a "
            "fresh implied ERP monthly on his Substack (aswathdamodaran.substack.com, 'Data "
            "Update' posts). NOTE: the older implpr.html page is frozen at ~2016 — use histimpl."
        ),
    ),
)

# Marginal tax rate fallback (US federal statutory). Changes with tax law, not monthly,
# so it gets a much longer freshness window.
MARGINAL_TAX_RATE = SourcedDefault(
    value=0.21,
    provenance=Provenance(
        as_of=date(2026, 1, 1),
        source="US federal statutory corporate tax rate (IRC §11)",
        source_url="https://www.irs.gov/corporations",
        max_age_days=365,
        note="Add state/local, or use the firm's marginal rate where it operates.",
    ),
)

MARKET_DEFAULTS: dict[str, SourcedDefault] = {
    "risk_free_rate": RISK_FREE_RATE,
    "equity_risk_premium": EQUITY_RISK_PREMIUM,
    "marginal_tax_rate": MARGINAL_TAX_RATE,
}


def market_staleness_warnings(today: date | None = None) -> list[str]:
    """Refresh nudges for any market default past its freshness window."""
    out: list[str] = []
    for label, default in MARKET_DEFAULTS.items():
        warning = default.staleness_warning(label, today)
        if warning:
            out.append(warning)
    return out
