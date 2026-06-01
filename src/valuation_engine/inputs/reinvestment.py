"""Free cash flows and the reinvestment rate.

Sign convention for these pure functions: ``capex``, ``depreciation`` and
``change_in_working_capital`` are positive magnitudes (cash invested), and
``net_debt_issued`` is positive when the firm borrows on net. The engines (Phase 3)
handle pulling correctly-signed figures out of the statements.
"""
from __future__ import annotations

from valuation_engine.inputs.base import Estimate


def fcff(
    ebit: float,
    tax_rate: float,
    capex: float,
    depreciation: float,
    change_in_working_capital: float,
) -> Estimate:
    """FCFF = EBIT(1 - t) - (capex - depreciation) - ΔWC."""
    nopat = ebit * (1.0 - tax_rate)
    net_capex = capex - depreciation
    value = nopat - net_capex - change_in_working_capital
    return Estimate(
        value=value,
        rationale=(
            f"FCFF = EBIT(1-t) - (capex-depr) - dWC = {nopat:,.0f} - {net_capex:,.0f} - "
            f"{change_in_working_capital:,.0f} = {value:,.0f}."
        ),
        inputs_used={
            "nopat": nopat,
            "net_capex": net_capex,
            "change_in_working_capital": change_in_working_capital,
        },
    )


def fcfe(
    fcff_value: float,
    interest_expense: float,
    tax_rate: float,
    net_debt_issued: float,
) -> Estimate:
    """FCFE = FCFF - interest(1 - t) + net debt issued."""
    after_tax_interest = interest_expense * (1.0 - tax_rate)
    value = fcff_value - after_tax_interest + net_debt_issued
    return Estimate(
        value=value,
        rationale=(
            f"FCFE = FCFF - interest(1-t) + net debt issued = {fcff_value:,.0f} - "
            f"{after_tax_interest:,.0f} + {net_debt_issued:,.0f} = {value:,.0f}."
        ),
        inputs_used={"after_tax_interest": after_tax_interest, "net_debt_issued": net_debt_issued},
    )


def reinvestment_rate(
    net_capex: float,
    change_in_working_capital: float,
    nopat: float,
) -> Estimate:
    """Reinvestment rate = (net capex + ΔWC) / NOPAT."""
    if nopat == 0:
        raise ValueError("NOPAT is zero; reinvestment rate is undefined")
    rate = (net_capex + change_in_working_capital) / nopat
    return Estimate(
        value=rate,
        rationale=(
            f"Reinvestment rate = (net capex + dWC)/NOPAT = ({net_capex:,.0f} + "
            f"{change_in_working_capital:,.0f})/{nopat:,.0f} = {rate:.1%}."
        ),
        inputs_used={
            "net_capex": net_capex,
            "change_in_working_capital": change_in_working_capital,
            "nopat": nopat,
        },
    )
