"""Canonical financial-statement container.

`Financials` holds the three statements as pandas DataFrames *after* a provider has
normalized them onto the canonical row labels below. Engines read these labels and
never touch a provider's raw (e.g. yfinance) names — the normalization step in the
data layer (Phase 1) is the single place that mapping lives.

Phase 0: this is a pure, declarative data container. No extraction / derivation logic
lives here yet; line-item accessors and cleaning (R&D capitalization, one-time-item
stripping, lease handling) arrive with the input modules in Phase 2.
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

# --- Canonical statement row labels -------------------------------------------------
# The contract between the data layer and the engines. A provider's normalization step
# maps source labels onto these; engines look up only these names. Extend as needed.
CANONICAL_INCOME_ROWS: tuple[str, ...] = (
    "TotalRevenue",
    "CostOfRevenue",
    "GrossProfit",
    "ResearchAndDevelopment",
    "SellingGeneralAndAdministrative",
    "OperatingIncome",  # ~ EBIT before normalization adjustments
    "EBIT",
    "EBITDA",
    "InterestExpense",
    "PretaxIncome",
    "TaxProvision",
    "NetIncome",
    "DilutedShares",
)
CANONICAL_BALANCE_ROWS: tuple[str, ...] = (
    "TotalAssets",
    "CurrentAssets",
    "CurrentLiabilities",
    "CashAndCashEquivalents",
    "TotalDebt",
    "LongTermDebt",
    "CurrentDebt",
    "CommonStockEquity",  # book value of equity
    "MinorityInterest",
    "InvestedCapital",
)
CANONICAL_CASHFLOW_ROWS: tuple[str, ...] = (
    "OperatingCashFlow",
    "CapitalExpenditure",
    "Depreciation",  # D&A
    "ChangeInWorkingCapital",
    "FreeCashFlow",
)


class Financials(BaseModel):
    """Normalized historical statements for one company (annual + quarterly).

    Each DataFrame is indexed by canonical line-item label (see the ``CANONICAL_*``
    tuples) with one column per fiscal-period end date, most recent first.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ticker: str
    currency: str | None = None
    fiscal_year_end: str | None = None

    # Annual statements (>= 5 years of history expected).
    income_statement: pd.DataFrame | None = None
    balance_sheet: pd.DataFrame | None = None
    cash_flow: pd.DataFrame | None = None

    # Quarterly statements (used to build trailing-twelve-month figures).
    income_statement_quarterly: pd.DataFrame | None = None
    balance_sheet_quarterly: pd.DataFrame | None = None
    cash_flow_quarterly: pd.DataFrame | None = None

    # Free-form notes from the data layer (e.g. "FY2023 restated", "reported in KRW").
    notes: list[str] = Field(default_factory=list)
