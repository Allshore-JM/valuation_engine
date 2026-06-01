# Build plan — Phases 1–6 (file-by-file)

Roadmap for `valuation_engine`, derived from the build framework. **Phases 0–6 — the full
v1 build — are done and green (110 tests: 109 offline + 1 gated live).** Phase 7 (real
options / special-case firms) remains deferred by design. Each phase below lists the *new*
files it adds, the
key public signatures, the formulas/discipline it must enforce, the design decisions
already defaulted, and the deliverable test that proves the phase.

Build bottom-up: every phase is testable before the next depends on it.

---

## Cross-cutting conventions (decided once, used everywhere)

- **`Estimate` (inputs layer).** Every input-estimation function returns a typed
  `Estimate(value: float, rationale: str, inputs_used: dict)` so the final report is
  auditable. Rationales flow into `Assumptions.rationales`.
- **`ValuationResult` (engines layer).** Every DCF engine returns
  `ValuationResult(value_per_share, equity_value, firm_value | None, projection:
  pd.DataFrame, terminal_value, terminal_value_share, discount_rate, warnings)`.
- **`FixtureProvider`.** A `DataProvider` that replays a recorded JSON snapshot. Built
  in Phase 1 and reused as the deterministic, offline golden-case input for every
  later phase's tests. **No test ever hits the live network** (one `@integration`
  test, skipped by default, is the only exception).
- **Override flow (auditable).** `provider.manual_override(field, value)` pins raw
  data; `Assumptions.*` fields pin engine inputs; Phase 6 CLI flags map to
  `Assumptions` overrides. Every pin is recorded so the report can show it.
- **Consistency checks are assertions, not comments.** Stable `g <= rf`; stable
  reinvestment `= g / ROC`; FCFF-equity ≈ FCFE within tolerance. They live in code and
  fail loudly.

---

## Phase 1 — Data layer (yfinance) ✅ DONE  → framework §3, Phase-1 prompt

**Goal:** turn a ticker into a populated `Company` (+ `Financials`), offline-testable.

**Delivered:** `snapshot.py` (RawSnapshot — the JSON format shared by cache + fixtures),
`normalize.py` (the one source→canonical label map), `cache.py`, `yfinance_provider.py`,
`fixture_provider.py`; committed `fixtures/AAPL.json` + `KO.json`; `conftest.py` +
`test_data_provider.py`. 25 offline tests + 1 gated live test, all green. `snapshot.py`
is the one module added beyond the original list — the raw recording earned its own file.

```
src/valuation_engine/data/
├── yfinance_provider.py   # YFinanceProvider(DataProvider): fetch + assemble Company/Financials
├── fixture_provider.py    # FixtureProvider(DataProvider): replay a saved snapshot, offline
├── normalize.py           # THE ONE place yfinance row/col labels -> canonical labels
├── cache.py               # disk cache keyed by (ticker, date) + polite rate-limiting
└── fixtures/
    ├── AAPL.json          # recorded snapshots, committed, used by the test suite
    └── KO.json
tests/
├── conftest.py            # pytest fixture exposing a FixtureProvider
└── test_data_provider.py  # fixture-based assertions + 1 skippable @integration live test
```

**Key signatures**
- `YFinanceProvider.get_company(ticker) -> Company` / `.get_financials(ticker) -> Financials`
  / `.get_peers(tickers) -> list[Company]` / `.manual_override(field, value)`.
- `normalize.income_statement(raw_df) -> pd.DataFrame` (and balance/cashflow), mapping
  source labels onto `CANONICAL_*` from `domain/financials.py`.

**Must do**
- Treat every `.info`/`.fast_info` field as optional; fall back to statement-derived
  values. Never assume a key exists.
- Detect special cases and push to `Company.data_warnings`: negative book equity,
  negative EBITDA, financial-sector firm, missing statements (framework §7 / Phase 7).

**Decisions defaulted**
- **Cache = a small custom JSON/parquet disk cache** keyed by ticker+date, *not*
  `requests-cache`. Reason: yfinance 1.4.1 fetches via `curl_cffi`, which
  `requests-cache` does not wrap cleanly. (Re-evaluate if yfinance exposes a
  cache-friendly session.)
- Fixtures (AAPL, KO) are **recorded live during this phase** by me, then committed;
  tests replay them.

**Deliverable test:** `FixtureProvider` yields a `Company` with normalized statements;
canonical labels resolve; a negative-equity fixture raises the right warning.

---

## Phase 2 — Input-estimation modules ✅ DONE  → framework §4, Phase-2 prompt

**Goal:** each input as a pure `(...) -> Estimate`, with consistency assertions.

**Delivered:** `base.py` (`Estimate`), and riskfree, erp, beta (Hamada bottom-up +
regression), cost_of_equity (CAPM), cost_of_debt (synthetic rating), cost_of_capital
(WACC), earnings (R&D capitalization, effective tax, EBIT normalization, lease PV),
reinvestment (FCFF/FCFE/reinvestment rate), growth, terminal_value (Gordon + stable-phase
assertions). Filled `config/defaults.py` tables (rating spreads, sector betas).
**Added per request:** `config/provenance.py` + `config/market.py` — every market default
(rf, ERP, tax) and Damodaran table carries an `as_of` date, refresh source/URL, and
`max_age_days`; `config.all_staleness_warnings()` nudges when stale (the ERP default,
set 2026-01-01, warns today). Tests: `test_inputs.py` + `test_market_defaults.py` (56 green).

```
src/valuation_engine/inputs/
├── base.py            # Estimate model + helpers
├── riskfree.py        # risk_free_rate(currency, override) -> Estimate
├── erp.py             # historical_erp(); implied_erp(index_level, expected_cfs) [hook]
├── beta.py            # bottom_up_beta(sector, D, E, tax); regression_beta(prices, index)
├── cost_of_equity.py  # capm(rf, beta, erp) = rf + beta*erp
├── cost_of_debt.py    # synthetic_rating(coverage); default_spread(rating); cost_of_debt(...)
├── cost_of_capital.py # wacc(ke, kd_aftertax, E, D) at MARKET-value weights
├── earnings.py        # capitalize_rd(); normalize_ebit(); one-time strip; lease handling
├── reinvestment.py    # fcff(); fcfe(); reinvestment_rate()
├── growth.py          # g_firm = reinvest*ROC ; g_equity = retention*ROE
└── terminal_value.py  # gordon TV + consistency assertions (g<=rf, reinvest=g/ROC)
src/valuation_engine/config/
└── defaults.py        # FILL the empty tables: SYNTHETIC_RATING_TABLE, SECTOR_UNLEVERED_BETA
tests/test_inputs.py   # unit tests + edge cases (zero growth, zero reinvest, neg coverage)
```

**Key formulas**
- Bottom-up beta (Hamada): `β_U = β_L / (1 + (1−t)·D/E)`; relever
  `β_L = β_U · (1 + (1−t)·D/E)` (assumes debt beta ≈ 0).
- Cost of debt: `(rf + default_spread) · (1 − t)`; spread from interest-coverage
  synthetic rating when no agency rating exists.
- WACC at market weights: `ke·E/(D+E) + kd_after·D/(D+E)`.
- FCFF `= EBIT(1−t) − (capex − depr) − ΔWC`; FCFE `= FCFF − int(1−t) − net debt repaid`.
- Earnings cleaning: capitalize R&D (amortize over a research life, add back to EBIT
  and to invested capital). **Note the modern lease regime:** post-2019 operating
  leases are mostly already on the balance sheet — handle both the old (capitalize)
  and new (already-capitalized) cases.

**Deliverable test:** each module's golden value matches a hand-computed figure;
`terminal_value` raises when `g > rf`; zero-reinvestment reduces to a flat perpetuity.

---

## Phase 3 — DCF engines ✅ DONE  → framework §5a, Phase-3 prompt

**Goal:** multi-stage FCFF / FCFE / DDM that agree on a golden case.

**Delivered:** `base.py` (`ValuationResult`, latest-non-null extraction, phase
resolution + schedule, `resolve_stable` reusing Phase 2's checks, the shared
`finalize_equity` per-share bridge, TV-share warning); `fcff.py`, `fcfe.py`, `ddm.py`;
plus `assemble.py` (`baseline_assumptions` wires the Phase 2 inputs into a starting
`Assumptions`; Phase 6 reuses it). **Design choice:** FCFE is derived from FCFF with a
constant-debt-ratio financing model, so an unlevered firm gives FCFF ≡ FCFE exactly
(tested to 1e-9) and AAPL converges to −3.7% (FCFF $139.62 vs FCFE $144.82; DDM $31.96).
Tests `test_engines.py`: perpetuity reduction, cash/debt bridge, unlevered invariant,
discount/growth monotonicity, stable-g>rf raises, TV warning, AAPL convergence, DDM floor
< FCFE, KO DDM. 70 offline green.

```
src/valuation_engine/engines/
├── base.py    # ValuationResult; project_phases(assumptions, base) -> df; discount(); per-share bridge
├── fcff.py    # value_fcff(company, assumptions) -> ValuationResult  (firm -> equity via net debt)
├── fcfe.py    # value_fcfe(company, assumptions) -> ValuationResult  (equity directly)
└── ddm.py     # value_ddm(company, assumptions) -> ValuationResult   (dividends, cost of equity)
tests/test_engines.py
```

**Plumbing (in `base.py`)**
- `project_phases` walks high-growth → optional transition → stable, deriving growth
  from fundamentals each phase.
- **Per-share bridge centralized (framework point 5):** equity value − options value −
  noncontrolling interest + nonoperating assets, then ÷ diluted shares.
- `terminal_value_share` computed and surfaced for the TV-dominance warning.

**Discipline:** FCFF discounts at WACC; FCFE/DDM at cost of equity. The two should
converge — a divergence beyond tolerance is a bug or inconsistent assumption.

**Deliverable test:** FCFF-derived equity/share and FCFE/share agree within tolerance
on the AAPL fixture; raising the discount rate lowers value (monotonicity); raising
stable g raises value; zero-growth+zero-reinvestment ⇒ perpetuity.

---

## Phase 4 — Relative engine ✅ DONE  → framework §5b, Phase-4 prompt

**Goal:** the book's four-step discipline, not naive peer averaging.

**Delivered:** `inputs/multiples.py` (`compute_multiples` → P/E, PEG, EV/EBITDA, EV/Sales,
P/B + companion variables, all derived from statements/market so it is provider-agnostic);
`engines/relative.py` (four-step: distribution → numpy `lstsq` regression on the companion
variable → predict fair multiple → apply via the equity/enterprise bridge; graceful median
fallback when peers lack spread or the regression predicts a non-positive multiple).
Extracted `statements.py` (`latest_valid`, `historical_growth`) to avoid an inputs↔engines
import cycle. Committed peer fixtures: 5 Technology (AAPL) + 4 Consumer-Defensive (KO).
Tests `test_relative.py`: regression recovers known coefficients, equity/enterprise apply,
multiples on AAPL, four-step on both peer sets, insufficient-peer fallback. 80 offline green.
Demo: AAPL relative ≈ $317–463/sh (near/above the $312 price) vs DCF $140–145 — the exact
intrinsic-vs-relative tension Phase 5 reconciles.

```
src/valuation_engine/
├── inputs/multiples.py     # compute P/E, PEG, EV/EBITDA, EV/Sales, P/B for a Company
└── engines/relative.py     # define -> distribution -> regress companion var -> predict -> apply
tests/test_relative.py
```

**Four steps (enforced):** (1) consistent multiple (equity multiples ↔ equity value;
EV multiples ↔ firm value); (2) describe the sector distribution (median/spread/
outliers); (3) regress the multiple on its companion variable (P/E↔growth&risk;
EV/EBITDA↔reinvest&ROC; P/B↔ROE) to predict a *fair* multiple; (4) apply it to the
target's metric.

**Decision defaulted:** regression via **numpy `lstsq`/`polyfit`** — no new dependency.
(`statsmodels` later if we want richer diagnostics.)

**Deliverable test:** on a synthetic peer set with a known linear relationship, the
regression recovers the coefficients and the predicted multiple is correct.

---

## Phase 5 — Reconciliation & report ✅ DONE  → framework §6, Phase-5 prompt

**Delivered:** `reconcile/{triangulate,sensitivity,scenarios,monte_carlo,implied,perturb}.py`
and `report/{markdown,html}.py`. `triangulate` lays FCFF/FCFE/DDM + relative against price
with per-method upside + margin of safety; `tornado` ranks inputs by value swing (WACC
dominates); `scenario_analysis` (bull/base/bear); seeded `monte_carlo` → value range +
P(value>price); `implied_growth` reverse-DCF. `render_report` emits the full markdown
report (disclaimer, staleness warnings, assumptions, all estimates, sensitivity, scenarios,
MC, reverse DCF, TV-dominance flag); `render_html` wraps it. Tests `test_reconcile.py`
(89 offline green). Live AAPL report: price implies 36.8% growth vs the 15.1% assumption.

```
src/valuation_engine/reconcile/
├── triangulate.py   # FCFF vs FCFE/DDM vs relative vs price -> table + over/under %
├── sensitivity.py   # one-at-a-time tornado over WACC, stable g, margin, ROC
├── scenarios.py     # bull / base / bear assumption sets -> values
├── monte_carlo.py   # distributions over key inputs -> value range + P(value > price)
└── implied.py       # reverse-DCF: what growth/risk does the current price imply?
src/valuation_engine/report/
├── markdown.py      # full report: every assumption, projection tables, 3 values, warnings
└── html.py          # optional
tests/test_reconcile.py
```

**Report must list:** every assumption + rationale, the projection tables, the three
value estimates with over/under-valuation vs price, sensitivity results, margin of
safety (price as % of value), and the **terminal-value-share warning** when TV is an
outsized share of value.

**Decision defaulted:** **markdown first** (+ optional HTML). **PDF deferred** — it
needs an extra dep (weasyprint/reportlab).

**Deliverable test:** a snapshot of the rendered markdown for the AAPL fixture is
stable; sensitivity orders inputs by value swing; MC reports a coherent P(value>price).

---

## Phase 6 — CLI + polish ✅ DONE  → framework Phase-6 prompt, §7

**Delivered:** `pipeline.py` (`run_valuation(ticker, provider, overrides=...) -> ValuationRun`,
shared by CLI + notebooks; component overrides flow through ke/kd/WACC, direct overrides pin
finished fields); `cli.py` (`typer` app — `valuate TICKER` with `--peers`, `--out`, `--fmt`,
`--offline`, override flags `--wacc/--erp/--tax/--high-growth/…`, `--margin-of-safety`,
`--no-monte-carlo`); `valuate` entry point wired in `pyproject.toml`. Golden tests pin
AAPL/KO FCFF+FCFE; invariant tests (stable g≤rf, tax∈[0,1), FCFF≈FCFE, TV share∈(0,1),
WACC↑→value↓) across both firms; CLI tests via typer `CliRunner` (offline run, HTML out,
override, error exit). `.github/workflows/ci.yml` runs the offline suite on push. 109 offline
tests green. Demo: `valuate AAPL --offline --peers MSFT,NVDA,ORCL,CRM,AVGO --margin-of-safety 0.2`.

```
src/valuation_engine/
├── pipeline.py   # run_valuation(ticker, provider, overrides) -> Report  (shared by CLI + notebook/API)
└── cli.py        # typer app: `valuate TICKER`
pyproject.toml    # add [project.scripts] valuate = "valuation_engine.cli:app"
tests/
├── test_golden_cases.py   # 3–5 firms reproduced within tolerance
└── test_invariants.py     # g<=rf always; FCFF≈FCFE; per-share >= 0 for healthy firms; monotonicities
.github/workflows/ci.yml   # optional: run pytest on push
```

**CLI flags:** override key assumptions (`--wacc`, `--stable-growth`, `--erp`,
`--tax`, …), pick engines (`--engine fcff,fcfe,relative`), choose report format, set
margin-of-safety threshold.

**Deliverable:** `valuate AAPL` runs the full pipeline and writes a report; golden +
invariant suites are green.

---

## Decisions already defaulted (flag any you'd change)

| # | Topic | Default for v1 | Alternative |
|---|---|---|---|
| 1 | Cache | custom JSON/parquet disk cache | requests-cache (curl_cffi friction) |
| 2 | Risk-free & ERP source | config default + manual override | live fetch (Treasury/FRED) + implied-ERP solver |
| 3 | Relative regression | numpy `lstsq` | add `statsmodels` |
| 4 | Report format | markdown (+ optional HTML) | add PDF (weasyprint/reportlab) |
| 5 | Beta | bottom-up (Hamada), regression as cross-check | regression beta as primary |
| 6 | Golden tickers | AAPL (FCFF), KO (DDM), + 1 TBD | your picks |

## Open questions worth your input before/while building

- **Q1 — market data:** OK to start with config-default rf/ERP + overrides (Q2 in
  table), or do you want live macro fetch now?
- **Q2 — golden cases:** any specific firms/sectors you care about validating against?
  (sector choice shapes what edge cases we cover)
- **Q3 — report:** markdown-only fine for v1, or is HTML/PDF a near-term must?
- **Q4 — regression:** numpy-only, or add `statsmodels` for nicer regression output?

## Deferred (framework Phase 7)

Real-options / contingent-claim valuation and special-case routing (financial-service
firms via equity cash flows, distressed, young-firm, negative-earnings). The data
layer (Phase 1) **detects** these and warns; the default pipeline does not pretend to
handle them.
