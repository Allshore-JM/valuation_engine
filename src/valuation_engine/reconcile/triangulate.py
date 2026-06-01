"""Triangulate intrinsic (FCFF/FCFE/DDM) and relative values against market price."""
from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from valuation_engine.domain import Assumptions, Company
from valuation_engine.engines import relative_valuation, value_ddm, value_fcfe, value_fcff


class ValueEstimate(BaseModel):
    method: str
    category: str  # "intrinsic" | "relative"
    value_per_share: float
    upside_vs_price: float | None = None  # (value - price) / price; +ve => stock below value


class Triangulation(BaseModel):
    ticker: str
    price: float | None = None
    estimates: list[ValueEstimate] = []
    intrinsic_median: float | None = None
    relative_median: float | None = None
    overall_median: float | None = None
    margin_of_safety: float | None = None  # (central intrinsic value - price) / value
    warnings: list[str] = []


def _upside(value: float, price: float | None) -> float | None:
    return (value - price) / price if price else None


def _median(values: list[float]) -> float | None:
    return float(np.median(values)) if values else None


def triangulate(
    company: Company,
    assumptions: Assumptions,
    peers=None,
    *,
    multiples=("pe", "pb", "ev_ebitda", "ev_sales"),
) -> Triangulation:
    price = company.price
    result = Triangulation(ticker=company.ticker, price=price)

    for name, engine in (("FCFF", value_fcff), ("FCFE", value_fcfe), ("DDM", value_ddm)):
        try:
            r = engine(company, assumptions)
        except Exception as exc:  # noqa: BLE001 - DDM may not apply, etc.
            result.warnings.append(f"{name} skipped: {exc}")
            continue
        result.estimates.append(ValueEstimate(
            method=name, category="intrinsic",
            value_per_share=r.value_per_share, upside_vs_price=_upside(r.value_per_share, price),
        ))
        result.warnings.extend(f"{name}: {w}" for w in r.warnings)

    if peers:
        for key, rv in relative_valuation(company, peers, multiples).items():
            value = rv.implied_value_per_share_regression or rv.implied_value_per_share_median
            if value and value > 0:
                result.estimates.append(ValueEstimate(
                    method=f"relative:{key}", category="relative",
                    value_per_share=value, upside_vs_price=_upside(value, price),
                ))

    intrinsic = [e.value_per_share for e in result.estimates if e.category == "intrinsic"]
    relative = [e.value_per_share for e in result.estimates if e.category == "relative"]
    result.intrinsic_median = _median(intrinsic)
    result.relative_median = _median(relative)
    result.overall_median = _median([e.value_per_share for e in result.estimates])

    central = result.intrinsic_median or result.overall_median
    if central and price:
        result.margin_of_safety = (central - price) / central
    return result
