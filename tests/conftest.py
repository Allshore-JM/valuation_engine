"""Shared fixtures + integration-test gating for the suite."""
from __future__ import annotations

import pytest

from valuation_engine.data import FixtureProvider


@pytest.fixture
def provider() -> FixtureProvider:
    """Offline DataProvider replaying committed snapshots — never hits the network."""
    return FixtureProvider()


@pytest.fixture
def aapl(provider: FixtureProvider):
    return provider.get_company("AAPL")


@pytest.fixture
def ko(provider: FixtureProvider):
    return provider.get_company("KO")


def pytest_collection_modifyitems(config, items):
    """Skip @integration (live-network) tests unless explicitly selected (-m integration)."""
    if "integration" in (config.option.markexpr or ""):
        return
    skip = pytest.mark.skip(reason="integration: needs network; run with -m integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
