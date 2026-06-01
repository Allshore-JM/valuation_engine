"""Valuation engines.

DCF (Phase 3): ``fcff.py``, ``fcfe.py``, ``ddm.py`` — project cash flows by phase,
compute a terminal value, discount at the matched rate, return a ``ValuationResult`` with
the full projection table. ``assemble.baseline_assumptions`` wires the Phase 2 inputs into
a starting ``Assumptions``.
Relative (Phase 4): ``relative.py``. ``real_options.py`` is deferred (Phase 7).
"""
from valuation_engine.engines.assemble import baseline_assumptions
from valuation_engine.engines.base import ValuationResult
from valuation_engine.engines.ddm import value_ddm
from valuation_engine.engines.fcfe import value_fcfe
from valuation_engine.engines.fcff import value_fcff
from valuation_engine.engines.relative import (
    RelativeValuation,
    linear_regression,
    relative_valuation,
    relative_value,
)

__all__ = [
    "RelativeValuation",
    "ValuationResult",
    "baseline_assumptions",
    "linear_regression",
    "relative_valuation",
    "relative_value",
    "value_ddm",
    "value_fcfe",
    "value_fcff",
]
