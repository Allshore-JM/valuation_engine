"""Relative valuation via the book's four-step discipline (framework §5b).

1. Define each multiple consistently (equity multiples on equity value, enterprise
   multiples on firm value).
2. Describe the peer distribution (median, spread, quartiles).
3. Regress the multiple on its companion variable (P/E~growth, P/B~ROE, EV/EBITDA~ROC,
   EV/Sales~operating margin) to predict a *fair* multiple for the target — controlling
   for *why* firms trade at different multiples instead of grabbing one comp.
4. Apply the predicted multiple to the target's own metric -> implied value per share.
"""
from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from valuation_engine.domain import Company
from valuation_engine.inputs.multiples import compute_multiples

# multiple -> (basis, companion-variable attr, target-metric attr)
MULTIPLE_SPECS: dict[str, tuple[str, str, str]] = {
    "pe": ("equity", "earnings_growth", "net_income"),
    "pb": ("equity", "roe", "book_equity"),
    "ev_ebitda": ("enterprise", "roc", "ebitda"),
    "ev_sales": ("enterprise", "operating_margin", "revenue"),
}


class PeerStat(BaseModel):
    n: int
    median: float
    mean: float
    std: float
    minimum: float
    maximum: float
    q1: float
    q3: float


class Regression(BaseModel):
    driver: str
    slope: float
    intercept: float
    r_squared: float
    n: int

    def predict(self, x: float) -> float:
        return self.slope * x + self.intercept


class RelativeValuation(BaseModel):
    multiple: str
    basis: str
    driver: str
    distribution: PeerStat | None = None
    regression: Regression | None = None
    target_metric: float | None = None
    target_driver: float | None = None
    median_multiple: float | None = None
    predicted_multiple: float | None = None
    implied_value_per_share_median: float | None = None
    implied_value_per_share_regression: float | None = None
    warnings: list[str] = []


def describe(values) -> PeerStat:
    a = np.asarray(list(values), dtype=float)
    return PeerStat(
        n=int(a.size),
        median=float(np.median(a)),
        mean=float(a.mean()),
        std=float(a.std(ddof=1)) if a.size > 1 else 0.0,
        minimum=float(a.min()),
        maximum=float(a.max()),
        q1=float(np.percentile(a, 25)),
        q3=float(np.percentile(a, 75)),
    )


def linear_regression(xs, ys, driver: str = "x") -> Regression:
    """Ordinary least squares y = slope*x + intercept via numpy (no extra dependency)."""
    x = np.asarray(list(xs), dtype=float)
    y = np.asarray(list(ys), dtype=float)
    A = np.vstack([x, np.ones_like(x)]).T
    (slope, intercept), *_ = np.linalg.lstsq(A, y, rcond=None)
    yhat = slope * x + intercept
    ss_res = float(((y - yhat) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return Regression(driver=driver, slope=float(slope), intercept=float(intercept),
                      r_squared=r2, n=int(x.size))


def _apply_multiple(multiple_value: float, metric: float, basis: str, company: Company) -> float:
    if basis == "equity":
        equity_value = multiple_value * metric
    else:  # enterprise multiple -> EV, then bridge EV -> equity
        ev = multiple_value * metric
        equity_value = ev - (company.total_debt or 0.0) + (company.cash_and_equivalents or 0.0)
    shares = company.shares_outstanding
    return equity_value / shares if shares else float("nan")


def relative_value(target: Company, peers, multiple: str, *, min_peers: int = 3) -> RelativeValuation:
    """Run the four-step process for one multiple against a peer set."""
    if multiple not in MULTIPLE_SPECS:
        raise ValueError(f"unknown multiple {multiple!r}; choose from {sorted(MULTIPLE_SPECS)}")
    basis, driver_attr, metric_attr = MULTIPLE_SPECS[multiple]

    target_m = compute_multiples(target)
    peer_ms = [compute_multiples(p) for p in peers]
    target_metric = getattr(target_m, metric_attr)
    target_driver = getattr(target_m, driver_attr)

    result = RelativeValuation(
        multiple=multiple, basis=basis, driver=driver_attr,
        target_metric=target_metric, target_driver=target_driver,
    )

    # Step 2 — distribution of the multiple across peers.
    mult_values = [getattr(m, multiple) for m in peer_ms]
    mult_values = [v for v in mult_values if v is not None and v > 0]
    if not mult_values:
        result.warnings.append(f"no peer values available for {multiple}")
        return result
    dist = describe(mult_values)
    result.distribution = dist
    result.median_multiple = dist.median
    if target_metric is not None:
        result.implied_value_per_share_median = _apply_multiple(dist.median, target_metric, basis, target)

    # Steps 3–4 — regress on the companion variable, predict, apply.
    pairs = [
        (getattr(m, driver_attr), getattr(m, multiple))
        for m in peer_ms
        if getattr(m, driver_attr) is not None
        and getattr(m, multiple) is not None
        and getattr(m, multiple) > 0
    ]
    drivers = [d for d, _ in pairs]
    if len(pairs) >= min_peers and len({round(d, 9) for d in drivers}) > 1 and target_driver is not None:
        reg = linear_regression(drivers, [v for _, v in pairs], driver=driver_attr)
        result.regression = reg
        predicted = reg.predict(target_driver)
        if predicted <= 0:
            result.warnings.append(
                f"regression predicted a non-positive {multiple} ({predicted:.2f}); using median"
            )
            predicted = dist.median
        result.predicted_multiple = predicted
        if target_metric is not None:
            result.implied_value_per_share_regression = _apply_multiple(
                predicted, target_metric, basis, target
            )
    else:
        result.warnings.append(
            f"insufficient peer spread to regress {multiple} on {driver_attr}; using sector median"
        )
    return result


def relative_valuation(
    target: Company, peers, multiples=("pe", "pb", "ev_ebitda", "ev_sales")
) -> dict[str, RelativeValuation]:
    """Run every requested multiple; returns {multiple_key: RelativeValuation}."""
    return {m: relative_value(target, peers, m) for m in multiples}
