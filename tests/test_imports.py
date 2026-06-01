"""Phase 0 smoke tests: every package imports and the domain models instantiate.

No business logic is exercised yet — this just locks the skeleton in place so later
phases build on a known-good import graph.
"""
from __future__ import annotations

import importlib

import pytest

SUBPACKAGES = [
    "valuation_engine",
    "valuation_engine.domain",
    "valuation_engine.data",
    "valuation_engine.inputs",
    "valuation_engine.engines",
    "valuation_engine.reconcile",
    "valuation_engine.report",
    "valuation_engine.config",
    "valuation_engine.config.defaults",
]


@pytest.mark.parametrize("module_name", SUBPACKAGES)
def test_subpackage_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


def test_domain_models_instantiate() -> None:
    from valuation_engine.domain import Assumptions, Company, Financials, GrowthPhase

    financials = Financials(ticker="TEST")
    company = Company(ticker="TEST", name="Test Co", financials=financials)
    assumptions = Assumptions(
        risk_free_rate=0.04,
        phases=[GrowthPhase(name="stable", years=5, growth_rate=0.03)],
    )

    assert company.ticker == "TEST"
    assert company.financials is financials
    assert company.peers == []  # default_factory wired correctly
    assert assumptions.phases[0].name == "stable"
    assert assumptions.currency == "USD"  # default applied


def test_top_level_reexports() -> None:
    import valuation_engine as ve

    assert ve.__version__
    for name in ("Company", "Financials", "Assumptions", "GrowthPhase", "DataProvider"):
        assert hasattr(ve, name)


def test_dataprovider_is_runtime_checkable_protocol() -> None:
    from valuation_engine.data import DataProvider

    class _Dummy:
        def get_company(self, ticker: str): ...
        def get_financials(self, ticker: str): ...
        def get_peers(self, tickers): ...
        def manual_override(self, field, value): ...

    # Structural check: a class with the full method surface satisfies the protocol;
    # a bare object does not.
    assert isinstance(_Dummy(), DataProvider)
    assert not isinstance(object(), DataProvider)
