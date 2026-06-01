"""Compute valuation multiples and their companion variables for a company.

Everything is derived from the statements + market snapshot (not from yfinance's flaky
pre-computed ratios), so it works for any provider. Equity multiples (P/E, P/B) use
equity value; enterprise multiples (EV/EBITDA, EV/Sales) use enterprise value.
"""
from __future__ import annotations

from pydantic import BaseModel

from valuation_engine.domain import Company
from valuation_engine.inputs.earnings import effective_tax_rate
from valuation_engine.statements import historical_growth, latest_valid


class Multiples(BaseModel):
    """Valuation multiples plus the fundamentals that drive them and the raw metrics."""

    ticker: str
    sector: str | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None

    # multiples
    pe: float | None = None
    peg: float | None = None
    ev_ebitda: float | None = None
    ev_sales: float | None = None
    pb: float | None = None

    # companion variables (drivers)
    earnings_growth: float | None = None
    revenue_growth: float | None = None
    roe: float | None = None
    roc: float | None = None
    operating_margin: float | None = None
    beta: float | None = None

    # raw target metrics (denominators) used when applying a multiple
    net_income: float | None = None
    book_equity: float | None = None
    ebitda: float | None = None
    revenue: float | None = None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or not denominator or denominator <= 0:
        return None
    return numerator / denominator


def compute_multiples(company: Company) -> Multiples:
    fin = company.financials
    inc = fin.income_statement if fin else None
    bs = fin.balance_sheet if fin else None

    net_income = latest_valid(inc, "NetIncome")
    revenue = latest_valid(inc, "TotalRevenue")
    ebitda = latest_valid(inc, "EBITDA")
    ebit = latest_valid(inc, "EBIT")
    book_equity = latest_valid(bs, "CommonStockEquity")
    invested_capital = latest_valid(bs, "InvestedCapital")

    mcap = company.market_cap
    ev = (
        mcap + (company.total_debt or 0.0) - (company.cash_and_equivalents or 0.0)
        if mcap is not None
        else None
    )

    tax = effective_tax_rate(
        latest_valid(inc, "TaxProvision") or 0.0, latest_valid(inc, "PretaxIncome") or 0.0
    ).value
    nopat = ebit * (1.0 - tax) if ebit is not None else None

    earnings_growth = historical_growth(inc, "NetIncome")
    revenue_growth = historical_growth(inc, "TotalRevenue")
    growth_for_peg = earnings_growth if (earnings_growth and earnings_growth > 0) else revenue_growth

    pe = _ratio(mcap, net_income)
    peg = (
        pe / (growth_for_peg * 100.0)
        if (pe is not None and growth_for_peg and growth_for_peg > 0)
        else None
    )

    return Multiples(
        ticker=company.ticker,
        sector=company.sector,
        market_cap=mcap,
        enterprise_value=ev,
        pe=pe,
        peg=peg,
        ev_ebitda=_ratio(ev, ebitda),
        ev_sales=_ratio(ev, revenue),
        pb=_ratio(mcap, book_equity),
        earnings_growth=earnings_growth,
        revenue_growth=revenue_growth,
        roe=_ratio(net_income, book_equity),
        roc=_ratio(nopat, invested_capital),
        operating_margin=_ratio(ebit, revenue),
        beta=company.beta,
        net_income=net_income,
        book_equity=book_equity,
        ebitda=ebitda,
        revenue=revenue,
    )
