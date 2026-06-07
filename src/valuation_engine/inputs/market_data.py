"""Live market inputs fetched from yfinance, so rf and ERP stay current automatically.

Both fall back to the static config defaults when a fetch fails, so the engine always
has a usable value. Kept transparent: the live ERP is a simple, documented heuristic
(it can't replicate Damodaran's full implied-ERP pipeline without data yfinance lacks).
"""
from __future__ import annotations

from datetime import date

from valuation_engine.config.market import SourcedDefault
from valuation_engine.config.provenance import Provenance

# Damodaran's implied expected ANNUAL return on US stocks (start-of-2026 ≈ 8.41%). The live
# ERP is anchored to this minus the live risk-free rate, so the premium moves with rates.
# Update this occasionally from histimpl.html / Damodaran's monthly Substack data updates.
EXPECTED_MARKET_RETURN = SourcedDefault(
    value=0.0841,
    provenance=Provenance(
        as_of=date(2026, 1, 1),
        source="Damodaran implied expected return on US equities (start-of-2026)",
        source_url="https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histimpl.html",
        max_age_days=400,
        note="Anchor for the live ERP (= expected market return − live risk-free rate).",
    ),
)

# Sensible band for the live ERP so a stale anchor or odd rate can't produce a silly value.
ERP_FLOOR, ERP_CEILING = 0.030, 0.065


def live_risk_free_rate() -> float | None:
    """Current 10-year US Treasury yield via yfinance ^TNX (a decimal), or None on failure.

    ^TNX is quoted directly as the yield in percent (e.g. 4.54 → 4.54% → 0.0454).
    """
    try:
        import yfinance as yf

        value = float(yf.Ticker("^TNX").fast_info["lastPrice"])
    except Exception:  # noqa: BLE001
        return None
    rate = value / 100.0
    return rate if 0.0 < rate < 0.25 else None


def live_equity_risk_premium(risk_free_rate: float) -> float:
    """Live implied ERP = expected market return − risk-free rate, clamped to a sane band.

    A transparent heuristic: hold the expected return on stocks (anchored to Damodaran's
    latest implied figure) and let the *premium* move inversely with rates. Override it
    in the sidebar with Damodaran's exact monthly figure if you prefer.
    """
    erp = EXPECTED_MARKET_RETURN.value - risk_free_rate
    return min(max(erp, ERP_FLOOR), ERP_CEILING)
