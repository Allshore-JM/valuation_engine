"""The single place provider-specific labels become canonical domain objects.

A future provider (SEC EDGAR, FMP, Polygon, ...) only has to produce a ``RawSnapshot``
of the same shape and reuse everything here — no engine or normalization changes.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from valuation_engine.data.snapshot import (
    RawSnapshot,
    df_from_jsonable,
    series_from_jsonable,
)
from valuation_engine.domain import Company, Financials

# --- source label -> canonical label (first alias that is present wins) -------------
INCOME_ALIASES: dict[str, tuple[str, ...]] = {
    "TotalRevenue": ("Total Revenue", "Operating Revenue"),
    "CostOfRevenue": ("Cost Of Revenue", "Reconciled Cost Of Revenue"),
    "GrossProfit": ("Gross Profit",),
    "ResearchAndDevelopment": ("Research And Development",),
    "SellingGeneralAndAdministrative": ("Selling General And Administration",),
    "OperatingIncome": ("Operating Income", "Total Operating Income As Reported"),
    "EBIT": ("EBIT",),
    "EBITDA": ("EBITDA", "Normalized EBITDA"),
    "InterestExpense": ("Interest Expense", "Interest Expense Non Operating"),
    "PretaxIncome": ("Pretax Income",),
    "TaxProvision": ("Tax Provision",),
    "NetIncome": ("Net Income", "Net Income Common Stockholders"),
    "DilutedShares": ("Diluted Average Shares",),
}
BALANCE_ALIASES: dict[str, tuple[str, ...]] = {
    "TotalAssets": ("Total Assets",),
    "CurrentAssets": ("Current Assets",),
    "CurrentLiabilities": ("Current Liabilities",),
    "CashAndCashEquivalents": (
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
    ),
    "TotalDebt": ("Total Debt",),
    "LongTermDebt": ("Long Term Debt", "Long Term Debt And Capital Lease Obligation"),
    "CurrentDebt": ("Current Debt", "Current Debt And Capital Lease Obligation"),
    "CommonStockEquity": ("Common Stock Equity", "Stockholders Equity"),
    "MinorityInterest": ("Minority Interest",),
    "InvestedCapital": ("Invested Capital",),
}
CASHFLOW_ALIASES: dict[str, tuple[str, ...]] = {
    "OperatingCashFlow": (
        "Operating Cash Flow",
        "Cash Flow From Continuing Operating Activities",
    ),
    "CapitalExpenditure": ("Capital Expenditure", "Purchase Of PPE"),
    "Depreciation": (
        "Depreciation And Amortization",
        "Depreciation Amortization Depletion",
        "Reconciled Depreciation",
    ),
    "ChangeInWorkingCapital": ("Change In Working Capital",),
    "FreeCashFlow": ("Free Cash Flow",),
}


def _remap(raw: pd.DataFrame | None, aliases: dict[str, tuple[str, ...]]) -> pd.DataFrame | None:
    """Re-index a raw statement onto canonical labels, keeping rows that exist."""
    if raw is None or raw.empty:
        return None
    available = {str(i): i for i in raw.index}
    rows: dict[str, pd.Series] = {}
    for canonical, sources in aliases.items():
        for src in sources:
            if src in available:
                row = raw.loc[available[src]]
                if isinstance(row, pd.DataFrame):  # duplicate label -> take first
                    row = row.iloc[0]
                rows[canonical] = row
                break
    if not rows:
        return None
    out = pd.DataFrame(rows).T
    out.columns = raw.columns
    return out


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _first(info: dict, *keys: str) -> Any:
    for k in keys:
        v = info.get(k)
        if v is not None:
            return v
    return None


def _latest(df: pd.DataFrame | None, label: str) -> float | None:
    """Most recent (left-most column) value for a canonical label, or None."""
    if df is None or label not in df.index:
        return None
    val = df.loc[label].iloc[0]
    return None if pd.isna(val) else float(val)


def to_financials(snap: RawSnapshot) -> Financials:
    st = snap.statements
    fin_ccy = snap.info.get("financialCurrency") or snap.info.get("currency")
    return Financials(
        ticker=snap.ticker,
        currency=fin_ccy,
        income_statement=_remap(df_from_jsonable(st.get("income_stmt")), INCOME_ALIASES),
        balance_sheet=_remap(df_from_jsonable(st.get("balance_sheet")), BALANCE_ALIASES),
        cash_flow=_remap(df_from_jsonable(st.get("cashflow")), CASHFLOW_ALIASES),
        income_statement_quarterly=_remap(
            df_from_jsonable(st.get("quarterly_income_stmt")), INCOME_ALIASES
        ),
        balance_sheet_quarterly=_remap(
            df_from_jsonable(st.get("quarterly_balance_sheet")), BALANCE_ALIASES
        ),
        cash_flow_quarterly=_remap(
            df_from_jsonable(st.get("quarterly_cashflow")), CASHFLOW_ALIASES
        ),
    )


def detect_warnings(company: Company, fin: Financials) -> list[str]:
    """Flag firms the default going-concern DCF pipeline does not fit (framework §7)."""
    warnings: list[str] = []
    if fin.income_statement is None or fin.balance_sheet is None or fin.cash_flow is None:
        warnings.append("missing one or more financial statements; default DCF may not apply")
    bve = _latest(fin.balance_sheet, "CommonStockEquity")
    if bve is not None and bve < 0:
        warnings.append(
            "negative book value of equity; route to distressed / special-case path (deferred)"
        )
    ebitda = _latest(fin.income_statement, "EBITDA")
    ebit = _latest(fin.income_statement, "EBIT")
    if (ebitda is not None and ebitda < 0) or (ebit is not None and ebit < 0):
        warnings.append("negative EBIT/EBITDA; default going-concern DCF may not apply")
    if (company.sector or "").strip().lower() in {"financial services", "financials"}:
        warnings.append(
            "financial-service firm; value with equity cash flows (FCFE/DDM), not FCFF"
        )
    if company.price is None:
        warnings.append("no market price available")
    if company.shares_outstanding is None:
        warnings.append("no shares-outstanding figure available")
    return warnings


def to_company(snap: RawSnapshot, overrides: dict[str, Any] | None = None) -> Company:
    info, fast = snap.info, snap.fast_info
    fin = to_financials(snap)

    price = _first(fast, "lastPrice") or _first(info, "currentPrice", "regularMarketPrice")
    shares = _first(fast, "shares") or _first(info, "sharesOutstanding", "impliedSharesOutstanding")
    mcap = _first(fast, "marketCap") or _first(info, "marketCap")
    currency = _first(fast, "currency") or _first(info, "currency")

    total_debt = _first(info, "totalDebt")
    if total_debt is None:
        total_debt = _latest(fin.balance_sheet, "TotalDebt")
    cash = _first(info, "totalCash")
    if cash is None:
        cash = _latest(fin.balance_sheet, "CashAndCashEquivalents")

    company = Company(
        ticker=snap.ticker,
        name=_first(info, "longName", "shortName"),
        sector=_first(info, "sector"),
        industry=_first(info, "industry"),
        currency=currency,
        price=_to_float(price),
        shares_outstanding=_to_float(shares),
        market_cap=_to_float(mcap),
        beta=_to_float(_first(info, "beta")),
        total_debt=_to_float(total_debt),
        cash_and_equivalents=_to_float(cash),
        minority_interest=_latest(fin.balance_sheet, "MinorityInterest"),
        dividends=series_from_jsonable(snap.dividends),
        financials=fin,
    )
    company.data_warnings = detect_warnings(company, fin)

    for field, value in (overrides or {}).items():
        if hasattr(company, field):
            setattr(company, field, value)
            company.data_warnings.append(f"override applied: {field}={value!r}")
    return company
