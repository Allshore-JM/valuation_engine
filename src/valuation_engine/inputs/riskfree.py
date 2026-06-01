"""Risk-free rate: long-term government bond yield in the cash-flow currency."""
from __future__ import annotations

from datetime import date

from valuation_engine.config.market import RISK_FREE_RATE, SourcedDefault
from valuation_engine.inputs.base import Estimate


def risk_free_rate(
    override: float | None = None,
    *,
    default: SourcedDefault = RISK_FREE_RATE,
    today: date | None = None,
) -> Estimate:
    """User override if given, else the dated config default (with a staleness warning)."""
    if override is not None:
        return Estimate(
            value=float(override),
            rationale=f"Risk-free rate pinned to {override:.3%} by user override.",
            inputs_used={"override": override},
        )
    warnings = [w for w in [default.staleness_warning("risk_free_rate", today)] if w]
    return Estimate(
        value=default.value,
        rationale=(
            f"Risk-free rate = {default.value:.3%} from {default.source} "
            f"(as of {default.as_of.isoformat()}). Long-term govt bond yield in the "
            "cash-flow currency."
        ),
        inputs_used={
            "source": default.source,
            "as_of": default.as_of.isoformat(),
            "source_url": default.source_url,
        },
        warnings=warnings,
    )
