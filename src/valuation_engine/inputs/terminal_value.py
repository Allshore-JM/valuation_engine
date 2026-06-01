"""Terminal value (Gordon growth) with disciplined-stable-phase consistency checks."""
from __future__ import annotations

from valuation_engine.inputs.base import Estimate


def stable_phase_checks(
    stable_growth: float,
    discount_rate: float,
    *,
    risk_free_rate: float | None = None,
    stable_roc: float | None = None,
    strict: bool = True,
) -> list[str]:
    """Return (and optionally raise on) violations of stable-phase discipline.

    - growth must be below the discount rate (else the perpetuity diverges);
    - growth cannot exceed the risk-free rate (long-run economy cap), when rf is given;
    - implied reinvestment g/ROC must be < 100%, when a stable ROC is given.
    """
    problems: list[str] = []
    if stable_growth >= discount_rate:
        problems.append(
            f"stable growth {stable_growth:.2%} >= discount rate {discount_rate:.2%} "
            "(terminal value diverges)"
        )
    if risk_free_rate is not None and stable_growth > risk_free_rate + 1e-9:
        problems.append(
            f"stable growth {stable_growth:.2%} exceeds risk-free rate {risk_free_rate:.2%} "
            "(economy cap)"
        )
    if stable_roc is not None:
        reinvest = stable_growth / stable_roc if stable_roc else float("inf")
        if reinvest >= 1.0:
            problems.append(f"implied stable reinvestment g/ROC = {reinvest:.1%} >= 100%")
    if problems and strict:
        raise ValueError("terminal-value consistency failed: " + "; ".join(problems))
    return problems


def terminal_value(
    last_cashflow: float,
    stable_growth: float,
    discount_rate: float,
    *,
    risk_free_rate: float | None = None,
    stable_roc: float | None = None,
    strict: bool = True,
) -> Estimate:
    """Gordon-growth terminal value: CF_{n+1} / (r - g), with consistency checks.

    With ``strict=True`` (default) a violation raises; with ``strict=False`` the value is
    still returned and the violations come back as warnings.
    """
    warnings = stable_phase_checks(
        stable_growth,
        discount_rate,
        risk_free_rate=risk_free_rate,
        stable_roc=stable_roc,
        strict=strict,
    )
    next_cf = last_cashflow * (1.0 + stable_growth)
    tv = next_cf / (discount_rate - stable_growth)
    return Estimate(
        value=tv,
        rationale=(
            f"Terminal value (Gordon) = CF_n1/(r-g) = {next_cf:,.0f}/"
            f"({discount_rate:.2%}-{stable_growth:.2%}) = {tv:,.0f}."
        ),
        inputs_used={
            "last_cashflow": last_cashflow,
            "stable_growth": stable_growth,
            "discount_rate": discount_rate,
        },
        warnings=warnings,
    )
