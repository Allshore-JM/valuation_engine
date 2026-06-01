# valuation_engine

A Damodaran-style equity valuation engine: estimate the **intrinsic value** of a
publicly traded company (discounted cash flow) and cross-check it against a
**relative valuation** (peer multiples) and the current market price.

Built on the principles in Aswath Damodaran's *Investment Valuation* (3rd ed.).

> ⚠️ **Not investment advice.** Every output is a *model estimate* driven by
> assumptions, not a buy/sell recommendation. "Garbage in, garbage out" is the
> dominant failure mode in valuation, so the tool surfaces every input and lets you
> override it. A wrong cost of capital or stable-growth rate swamps any modeling
> sophistication. Treat a large gap between value and price as a prompt to
> re-examine your assumptions, not proof the market is wrong.

## Status

**v1 complete — Phases 0–6, 110 tests green.** Typed domain models + `DataProvider`
protocol (Phase 0); yfinance data layer with disk cache, normalization, an offline
`FixtureProvider`, committed fixtures (Phase 1); input modules with dated/sourced,
staleness-aware market defaults (Phase 2); multi-stage **FCFF/FCFE/DDM** engines sharing
one per-share bridge (Phase 3); **four-step relative valuation** (Phase 4); a
**reconciliation + markdown report** — triangulation, sensitivity, scenarios, Monte Carlo,
reverse-DCF (Phase 5); and a **`typer` CLI** (`valuate TICKER`) with full assumption
overrides, golden + invariant tests, and CI (Phase 6). Phase 7 (real options /
special-case firms) is deferred by design. See [PLAN.md](PLAN.md) for the file-by-file map.

Try it: `valuate AAPL --offline --peers MSFT,NVDA,ORCL,CRM,AVGO` (offline replays committed
fixtures; drop `--offline` for live yfinance).

## Layout

src-layout; tests import the package via `src` on `pythonpath` (configured in
`pyproject.toml`).

```
src/valuation_engine/
├── domain/      # typed objects: Company, Financials, Assumptions
├── data/        # DataProvider protocol (+ concrete providers, Phase 1)
├── inputs/      # risk-free, ERP, beta, cost of capital, earnings, growth, TV (Phase 2)
├── engines/     # FCFF, FCFE, DDM, relative (Phases 3–4)
├── reconcile/   # triangulation, sensitivity, scenarios, Monte Carlo (Phase 5)
├── report/      # markdown / html / pdf renderers (Phase 5)
└── config/      # reference tables: tax rates, rating→spread, sector betas
tests/           # import + invariant + golden-case tests
```

## Quick start

```powershell
# from the project root, using the bundled virtual environment
.\.venv\Scripts\python.exe -m pytest
```

(Or install the package into the venv editable: `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`.)

## Web app (Streamlit)

A point-and-click UI over the engine: pick a ticker, adjust every assumption with sliders,
and see the value-vs-price chart, sensitivity, scenarios, Monte Carlo, reverse-DCF, and a
downloadable report. The engine code is untouched — `streamlit_app.py` is a thin layer on top.

**Run locally:**

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[web]"            # once — installs Streamlit
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py     # opens http://localhost:8501
```

**Deploy (free, auto-redeploys on every `git push`):** sign in at
[share.streamlit.io](https://share.streamlit.io) with GitHub → **New app** → pick this repo,
branch `main`, main file `streamlit_app.py` → **Deploy**. Dependencies are read from
`requirements.txt`.

## Methodology guardrails (enforced in code, not just docs)

- **Match cash flow to discount rate** — FCFF ↔ cost of capital; FCFE / dividends ↔ cost of equity. The two should converge.
- **Growth is earned** — stable-phase growth is tied to `reinvestment × return`, not a free-floating input.
- **Disciplined terminal value** — stable growth ≤ risk-free rate; excess returns fade toward zero as a firm matures.
- **Value per share ≠ equity ÷ shares** — adjust for cash, cross-holdings, employee options, and minority interests first.
- **Show the range** — pair every point estimate with sensitivity / scenario / Monte Carlo analysis, and flag when terminal value dominates.

## Data

v1 uses [`yfinance`](https://github.com/ranaroussi/yfinance) (pinned) behind a
`DataProvider` protocol, so a paid feed (FMP, Polygon, Finnhub, EOD) or SEC EDGAR can
drop in by writing one class. yfinance is an unofficial scraper and can break without
warning — the test suite runs against recorded fixtures, never live calls.
