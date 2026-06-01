"""Input-estimation modules — each a pure function returning an auditable ``Estimate``.

Covers the framework's §4 inputs: risk-free rate, ERP, bottom-up/regression beta, CAPM
cost of equity, synthetic-rating cost of debt, market-weight WACC, earnings normalization
(R&D capitalization, one-time items, leases), FCFF/FCFE and the reinvestment rate,
fundamental growth, and terminal value with its consistency assertions.
"""
from valuation_engine.inputs.base import Estimate
from valuation_engine.inputs.beta import (
    bottom_up_beta,
    regression_beta,
    relever_beta,
    unlever_beta,
)
from valuation_engine.inputs.cost_of_capital import wacc
from valuation_engine.inputs.cost_of_debt import (
    cost_of_debt,
    interest_coverage_ratio,
    synthetic_rating,
)
from valuation_engine.inputs.cost_of_equity import capm
from valuation_engine.inputs.earnings import (
    RDCapitalization,
    capitalize_operating_leases,
    capitalize_rd,
    effective_tax_rate,
    normalize_ebit,
)
from valuation_engine.inputs.erp import equity_risk_premium, implied_erp
from valuation_engine.inputs.growth import (
    fundamental_growth_equity,
    fundamental_growth_firm,
    implied_reinvestment_rate,
)
from valuation_engine.inputs.multiples import Multiples, compute_multiples
from valuation_engine.inputs.reinvestment import fcfe, fcff, reinvestment_rate
from valuation_engine.inputs.riskfree import risk_free_rate
from valuation_engine.inputs.terminal_value import stable_phase_checks, terminal_value

__all__ = [
    "Estimate",
    "Multiples",
    "RDCapitalization",
    "compute_multiples",
    "bottom_up_beta",
    "capitalize_operating_leases",
    "capitalize_rd",
    "capm",
    "cost_of_debt",
    "effective_tax_rate",
    "equity_risk_premium",
    "fcfe",
    "fcff",
    "fundamental_growth_equity",
    "fundamental_growth_firm",
    "implied_erp",
    "implied_reinvestment_rate",
    "interest_coverage_ratio",
    "normalize_ebit",
    "regression_beta",
    "relever_beta",
    "reinvestment_rate",
    "risk_free_rate",
    "stable_phase_checks",
    "synthetic_rating",
    "terminal_value",
    "unlever_beta",
    "wacc",
]
