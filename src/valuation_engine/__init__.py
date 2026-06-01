"""valuation_engine — a Damodaran-style equity valuation engine.

Intrinsic (DCF: FCFF / FCFE / DDM) and relative (peer-multiple) valuation of public
equities, reconciled against the market price.

Every output is a model estimate driven by assumptions, NOT investment advice.
See the README for the full disclaimer and methodology.
"""
from __future__ import annotations

from valuation_engine.data import DataProvider
from valuation_engine.domain import Assumptions, Company, Financials, GrowthPhase

__version__ = "0.1.0"

__all__ = [
    "Assumptions",
    "Company",
    "DataProvider",
    "Financials",
    "GrowthPhase",
    "__version__",
]
