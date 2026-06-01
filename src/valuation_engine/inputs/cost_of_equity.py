"""Cost of equity via CAPM."""
from __future__ import annotations

from valuation_engine.inputs.base import Estimate


def capm(risk_free_rate: float, beta: float, equity_risk_premium: float) -> Estimate:
    """ke = rf + beta * ERP."""
    ke = risk_free_rate + beta * equity_risk_premium
    return Estimate(
        value=ke,
        rationale=(
            f"CAPM: ke = {risk_free_rate:.3%} + {beta:.2f}x{equity_risk_premium:.3%} "
            f"= {ke:.3%}."
        ),
        inputs_used={"rf": risk_free_rate, "beta": beta, "erp": equity_risk_premium},
    )
