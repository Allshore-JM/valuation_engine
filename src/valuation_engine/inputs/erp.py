"""Equity risk premium: published/implied premium over the risk-free rate."""
from __future__ import annotations

from datetime import date

from valuation_engine.config.market import EQUITY_RISK_PREMIUM, SourcedDefault
from valuation_engine.inputs.base import Estimate


def equity_risk_premium(
    override: float | None = None,
    *,
    default: SourcedDefault = EQUITY_RISK_PREMIUM,
    today: date | None = None,
) -> Estimate:
    """User override if given, else the dated config default (with a staleness warning)."""
    if override is not None:
        return Estimate(
            value=float(override),
            rationale=f"Equity risk premium pinned to {override:.3%} by user override.",
            inputs_used={"override": override},
        )
    warnings = [w for w in [default.staleness_warning("equity_risk_premium", today)] if w]
    return Estimate(
        value=default.value,
        rationale=(
            f"Equity risk premium = {default.value:.3%} from {default.source} "
            f"(as of {default.as_of.isoformat()})."
        ),
        inputs_used={
            "source": default.source,
            "as_of": default.as_of.isoformat(),
            "source_url": default.source_url,
        },
        warnings=warnings,
    )


def implied_erp(*args, **kwargs):
    """Back out the ERP from the index level and expected cash flows (deferred).

    A reverse-engineered implied premium (solve for the discount rate that prices the
    index) is a Phase 5 enhancement. For now use the published default or an override.
    """
    raise NotImplementedError(
        "implied_erp() is deferred to Phase 5; use equity_risk_premium() with the "
        "published default or a manual override."
    )
