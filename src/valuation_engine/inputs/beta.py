"""Beta: bottom-up (relevered sector beta) as the default, regression as a cross-check."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from valuation_engine.config.defaults import (
    SECTOR_UNLEVERED_BETA,
    SECTOR_UNLEVERED_BETA_PROVENANCE,
)
from valuation_engine.inputs.base import Estimate


def unlever_beta(levered_beta: float, debt_to_equity: float, tax_rate: float) -> float:
    """Hamada: strip leverage out of an equity beta (assumes debt beta ~ 0)."""
    return levered_beta / (1.0 + (1.0 - tax_rate) * debt_to_equity)


def relever_beta(unlevered_beta: float, debt_to_equity: float, tax_rate: float) -> float:
    """Hamada: add a firm's leverage onto an unlevered (asset) beta."""
    return unlevered_beta * (1.0 + (1.0 - tax_rate) * debt_to_equity)


def bottom_up_beta(
    sector: str | None,
    debt: float,
    equity: float,
    tax_rate: float,
    *,
    sector_betas: dict[str, float] | None = None,
    today: date | None = None,
) -> Estimate:
    """Relever the average unlevered beta for the firm's sector at its own D/E."""
    table = sector_betas or SECTOR_UNLEVERED_BETA
    warnings: list[str] = []
    unlevered = table.get(sector or "")
    if unlevered is None:
        unlevered = 1.0
        warnings.append(
            f"no unlevered beta for sector {sector!r}; defaulted to 1.0 — set manually."
        )
    staleness = SECTOR_UNLEVERED_BETA_PROVENANCE.staleness_warning("sector_unlevered_beta", today)
    if staleness:
        warnings.append(staleness)
    de = (debt / equity) if equity else 0.0
    levered = relever_beta(unlevered, de, tax_rate)
    return Estimate(
        value=levered,
        rationale=(
            f"Bottom-up beta: unlevered {unlevered:.2f} for {sector!r}, relevered at "
            f"D/E={de:.2f}, tax={tax_rate:.0%} -> {levered:.2f}."
        ),
        inputs_used={
            "unlevered_beta": unlevered,
            "debt_to_equity": de,
            "tax_rate": tax_rate,
        },
        warnings=warnings,
    )


def regression_beta(asset_prices, market_prices) -> Estimate:
    """Slope of asset returns on market returns: cov(asset, mkt) / var(mkt)."""
    ra = pd.Series(list(asset_prices), dtype="float64").pct_change(fill_method=None)
    rm = pd.Series(list(market_prices), dtype="float64").pct_change(fill_method=None)
    aligned = pd.concat([ra, rm], axis=1).dropna()
    if len(aligned) < 2:
        raise ValueError("need >= 3 aligned price points to regress a beta")
    cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])
    beta = float(cov[0, 1] / cov[1, 1])
    return Estimate(
        value=beta,
        rationale=f"Regression beta = cov(asset, mkt) / var(mkt) = {beta:.2f} over {len(aligned)} returns.",
        inputs_used={"n_returns": int(len(aligned))},
    )
