"""Earnings normalization: capitalize R&D, clean EBIT, estimate the tax rate.

Lease note: under ASC 842 / IFRS 16 (post-2019) operating leases are already on the
balance sheet, so the classic "capitalize operating leases" step is largely automatic.
``capitalize_operating_leases`` remains for older data / off-balance-sheet commitments.
"""
from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from valuation_engine.config.market import MARGINAL_TAX_RATE
from valuation_engine.inputs.base import Estimate


class RDCapitalization(BaseModel):
    """Result of treating R&D as a capital asset rather than an expense."""

    research_asset: float  # add to invested capital and book equity
    current_amortization: float
    current_rd: float
    ebit_adjustment: float  # add to reported EBIT
    rationale: str


def capitalize_rd(rd_by_year: Sequence[float], rd_life_years: int = 5) -> RDCapitalization:
    """Capitalize R&D over a research life (Damodaran).

    ``rd_by_year`` is most-recent-first: ``[R&D_t, R&D_{t-1}, ...]``.

    - research asset   = sum of unamortized R&D = Σ R&D_{t-i} * (life - i)/life, i=0..life
    - current amort     = Σ R&D_{t-i}/life, i=1..life
    - EBIT adjustment   = + current R&D (un-expense) − current amortization
    """
    rd = [float(x) for x in rd_by_year]
    life = int(rd_life_years)
    if life <= 0:
        raise ValueError("rd_life_years must be positive")
    current_rd = rd[0] if rd else 0.0
    research_asset = 0.0
    current_amortization = 0.0
    for i, amount in enumerate(rd[: life + 1]):
        research_asset += amount * max(0.0, (life - i) / life)
        if i >= 1:
            current_amortization += amount / life
    ebit_adjustment = current_rd - current_amortization
    return RDCapitalization(
        research_asset=research_asset,
        current_amortization=current_amortization,
        current_rd=current_rd,
        ebit_adjustment=ebit_adjustment,
        rationale=(
            f"Capitalized R&D over {life}y: research asset {research_asset:,.0f}, "
            f"current amortization {current_amortization:,.0f}, EBIT adj {ebit_adjustment:+,.0f}."
        ),
    )


def effective_tax_rate(
    tax_provision: float,
    pretax_income: float,
    *,
    marginal: float | None = None,
) -> Estimate:
    """tax / pretax, clamped to [0, marginal]; falls back to marginal if pretax <= 0."""
    marginal = MARGINAL_TAX_RATE.value if marginal is None else marginal
    warnings: list[str] = []
    if pretax_income and pretax_income > 0:
        eff = min(max(tax_provision / pretax_income, 0.0), marginal)
        rationale = (
            f"Effective tax = tax/pretax = {tax_provision:,.0f}/{pretax_income:,.0f} "
            f"= {eff:.1%} (clamped to [0, marginal {marginal:.0%}])."
        )
    else:
        eff = marginal
        warnings.append("non-positive pretax income; fell back to the marginal tax rate.")
        rationale = f"Pretax income <= 0; used marginal tax {marginal:.0%}."
    return Estimate(
        value=eff,
        rationale=rationale,
        inputs_used={"tax_provision": tax_provision, "pretax_income": pretax_income, "marginal": marginal},
        warnings=warnings,
    )


def normalize_ebit(
    reported_ebit: float,
    *,
    rd_adjustment: float = 0.0,
    one_time_items: float = 0.0,
) -> Estimate:
    """Clean EBIT: add the R&D-capitalization adjustment, strip one-time items.

    ``one_time_items``: net unusual amount included in reported EBIT (positive = one-time
    gains to remove; negative = one-time charges to add back).
    """
    normalized = reported_ebit + rd_adjustment - one_time_items
    return Estimate(
        value=normalized,
        rationale=(
            f"Normalized EBIT = reported {reported_ebit:,.0f} + R&D adj {rd_adjustment:+,.0f} "
            f"− one-time {one_time_items:+,.0f} = {normalized:,.0f}."
        ),
        inputs_used={
            "reported_ebit": reported_ebit,
            "rd_adjustment": rd_adjustment,
            "one_time_items": one_time_items,
        },
    )


def capitalize_operating_leases(
    lease_commitments: Sequence[float],
    pretax_cost_of_debt: float,
) -> Estimate:
    """PV of future operating-lease payments (year 1 first) — pre-2019 regime only.

    Modern filings already capitalize these; use only for older data or disclosed
    off-balance-sheet commitments.
    """
    pv = sum(
        pmt / (1.0 + pretax_cost_of_debt) ** year
        for year, pmt in enumerate(lease_commitments, start=1)
    )
    return Estimate(
        value=pv,
        rationale=(
            f"PV of {len(list(lease_commitments))} years of lease commitments at "
            f"{pretax_cost_of_debt:.3%} = {pv:,.0f} (pre-2019 regime; modern leases "
            "are already on the balance sheet)."
        ),
        inputs_used={"pretax_cost_of_debt": pretax_cost_of_debt},
    )
