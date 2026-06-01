"""Streamlit web UI for the equity valuation engine.

Run locally:   streamlit run streamlit_app.py
Deployed on:   Streamlit Community Cloud (auto-redeploys from the GitHub repo on push)

The engine code is untouched; this file is just a thin UI on top of it.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make src/ importable whether or not the package is pip-installed (e.g. on Streamlit Cloud).
sys.path.insert(0, str(Path(__file__).parent / "src"))

import altair as alt  # noqa: E402  (after sys.path tweak)
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from valuation_engine.config import all_staleness_warnings  # noqa: E402
from valuation_engine.data import FixtureProvider, YFinanceProvider  # noqa: E402
from valuation_engine.engines import baseline_assumptions  # noqa: E402
from valuation_engine.reconcile import (  # noqa: E402
    implied_growth,
    monte_carlo,
    scenario_analysis,
    tornado,
    triangulate,
)
from valuation_engine.reconcile.perturb import with_phase_growth  # noqa: E402
from valuation_engine.report import render_report  # noqa: E402

st.set_page_config(page_title="Equity Valuation Engine", page_icon="📈", layout="wide")

OFFLINE = "Offline (bundled fixtures)"
LIVE = "Live (yfinance)"
DEFAULT_PEERS = {"AAPL": ["MSFT", "NVDA", "ORCL", "CRM", "AVGO"],
                 "KO": ["PEP", "MNST", "KDP", "STZ"]}


@st.cache_data(show_spinner="Loading company data…")
def load_data(source: str, ticker: str, peers: tuple[str, ...]):
    provider = FixtureProvider() if source == OFFLINE else YFinanceProvider()
    company = provider.get_company(ticker)
    peer_companies = provider.get_peers(list(peers)) if peers else None
    return company, peer_companies, baseline_assumptions(company)


@st.cache_data(show_spinner=False)
def fixture_tickers() -> list[str]:
    return FixtureProvider().available()


# ----------------------------------------------------------------------------- header
st.title("📈 Equity Valuation Engine")
st.caption(
    "Intrinsic (DCF: FCFF · FCFE · DDM) and relative valuation, reconciled against the "
    "market price — built on Damodaran's *Investment Valuation*."
)
st.warning(
    "**Not investment advice.** Every number is a model estimate driven by the assumptions "
    "in the sidebar. Garbage in, garbage out — change an assumption and the answer changes."
)
for _w in all_staleness_warnings():
    st.info("🕓 " + _w)

# --------------------------------------------------------------------- sidebar: inputs
with st.sidebar:
    st.header("1 · Company")
    source = st.radio("Data source", [OFFLINE, LIVE], index=0,
                      help="Offline replays bundled fixtures instantly with no network. "
                           "Live fetches any ticker from Yahoo (can be slow / rate-limited).")
    if source == OFFLINE:
        available = fixture_tickers()
        ticker = st.selectbox("Ticker", [t for t in ("AAPL", "KO") if t in available] or available)
        peer_opts = [t for t in available if t != ticker]
        peers = st.multiselect("Peers (for relative valuation)", peer_opts,
                               default=[p for p in DEFAULT_PEERS.get(ticker, []) if p in peer_opts])
    else:
        ticker = (st.text_input("Ticker", value="AAPL") or "").strip().upper()
        peers_raw = st.text_input("Peers (comma-separated)", value="MSFT,NVDA,ORCL,CRM,AVGO")
        peers = [p.strip().upper() for p in peers_raw.split(",") if p.strip()]

if not ticker:
    st.stop()

try:
    company, peer_companies, base = load_data(source, ticker, tuple(peers))
except Exception as exc:  # noqa: BLE001
    st.error(f"Couldn't load **{ticker}**: {exc}")
    st.stop()

with st.sidebar:
    st.header("2 · Assumptions")
    st.caption("Suggested from the firm's own fundamentals — adjust any knob:")
    rf = float(base.risk_free_rate or 0.043)
    wacc = st.slider("WACC — FCFF discount", 0.03, 0.20, float(base.cost_of_capital or 0.09), 0.001, format="%.3f")
    ke = st.slider("Cost of equity — FCFE/DDM discount", 0.03, 0.25, float(base.cost_of_equity or 0.09), 0.001, format="%.3f")
    high_growth = st.slider("High-growth rate (5y)", -0.05, 0.40, float(base.phases[0].growth_rate or 0.08), 0.005, format="%.3f")
    sg_max = max(0.001, min(rf, wacc - 0.001, ke - 0.001))
    stable_growth = st.slider("Stable (perpetuity) growth", 0.0, float(sg_max),
                              float(min(base.stable_growth_rate or 0.02, sg_max)), 0.001, format="%.3f",
                              help="Capped at the risk-free rate and below the discount rate (long-run economy growth).")
    tax = st.slider("Tax rate", 0.0, 0.40, float(base.marginal_tax_rate or 0.21), 0.01, format="%.2f")
    with st.expander("Advanced"):
        stable_roc = st.slider("Stable ROC", 0.03, 0.30,
                               float(base.stable_return_on_capital or base.cost_of_capital or 0.09), 0.005, format="%.3f")
        st.caption(f"Baseline derived from rf = {rf:.2%}, ERP = {float(base.equity_risk_premium or 0):.2%}, "
                   f"beta = {float(base.beta or 0):.2f}.")

# Build the working assumptions from the sliders.
assumptions = base.model_copy(update={
    "cost_of_capital": wacc,
    "cost_of_equity": ke,
    "stable_growth_rate": stable_growth,
    "stable_return_on_capital": stable_roc,
    "marginal_tax_rate": tax,
})
assumptions = with_phase_growth(assumptions, high_growth)

try:
    tri = triangulate(company, assumptions, peer_companies)
    bars = tornado(company, assumptions)
    scenarios = scenario_analysis(company, assumptions)
except ValueError as exc:
    st.error(f"Those assumptions are inconsistent: {exc}")
    st.stop()

implied = None
try:
    implied = implied_growth(company, assumptions)
except Exception:  # noqa: BLE001
    pass

price = company.price

# --------------------------------------------------------------------------- headline
st.subheader(f"{company.name or ticker}  ·  {company.sector or ''}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Market price", f"{price:,.2f}" if price else "—")
c2.metric("Intrinsic median", f"{tri.intrinsic_median:,.2f}" if tri.intrinsic_median else "—")
c3.metric("Relative median", f"{tri.relative_median:,.2f}" if tri.relative_median else "—")
c4.metric("Margin of safety", f"{tri.margin_of_safety:.1%}" if tri.margin_of_safety is not None else "—",
          help="(intrinsic median − price) / intrinsic. Positive = price below value.")

tab_summary, tab_sens, tab_mc, tab_report = st.tabs(
    ["Summary", "Sensitivity & scenarios", "Monte Carlo", "Full report"]
)

# --------------------------------------------------------------------------- summary
with tab_summary:
    est_df = pd.DataFrame([
        {"method": e.method, "kind": e.category,
         "value / share": e.value_per_share, "upside vs price": e.upside_vs_price}
        for e in tri.estimates
    ])
    chart = alt.Chart(est_df).mark_bar().encode(
        x=alt.X("value / share:Q"),
        y=alt.Y("method:N", sort="-x"),
        color=alt.Color("kind:N", legend=alt.Legend(title=None)),
        tooltip=["method", alt.Tooltip("value / share:Q", format=",.2f"),
                 alt.Tooltip("upside vs price:Q", format="+.1%")],
    )
    if price:
        chart = chart + alt.Chart(pd.DataFrame({"price": [price]})).mark_rule(
            color="red", strokeDash=[4, 4]).encode(x="price:Q")
    st.altair_chart(chart, width="stretch")
    st.caption("Red dashed line = current market price.")
    st.dataframe(
        est_df, hide_index=True, width="stretch",
        column_config={
            "value / share": st.column_config.NumberColumn(format="%.2f"),
            "upside vs price": st.column_config.NumberColumn(format="percent"),
        },
    )
    if implied:
        st.info(
            f"**Reverse DCF —** the current price implies a high-growth-phase rate of "
            f"**{implied.implied_phase_growth:.1%}**, vs your assumed **{high_growth:.1%}**."
            + (f"  _{implied.note}_" if implied.note else "")
        )

# ------------------------------------------------------------ sensitivity & scenarios
with tab_sens:
    st.markdown("**Sensitivity — one input at a time (FCFF value / share)**")
    sdf = pd.DataFrame([{"input": b.input, "value @ low": b.low_value,
                         "value @ high": b.high_value, "swing": b.swing} for b in bars])
    st.altair_chart(
        alt.Chart(sdf).mark_bar().encode(
            x=alt.X("swing:Q", title="value swing"),
            y=alt.Y("input:N", sort="-x"),
            tooltip=[c for c in sdf.columns]),
        width="stretch",
    )
    st.dataframe(sdf, hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="%.2f")
                                for c in ("value @ low", "value @ high", "swing")})
    st.markdown("**Scenarios (FCFF)**")
    scen_df = pd.DataFrame([{"scenario": s.name, "value / share": s.value_per_share,
                             "discount": s.discount_rate, "stable g": s.stable_growth_rate,
                             "phase g": s.phase_growth} for s in scenarios])
    st.dataframe(scen_df, hide_index=True, width="stretch", column_config={
        "value / share": st.column_config.NumberColumn(format="%.2f"),
        "discount": st.column_config.NumberColumn(format="percent"),
        "stable g": st.column_config.NumberColumn(format="percent"),
        "phase g": st.column_config.NumberColumn(format="percent"),
    })

# --------------------------------------------------------------------------- monte carlo
with tab_mc:
    st.caption("Randomizes WACC, stable growth, phase growth and tax around your assumptions.")
    mc_n = st.slider("Iterations", 500, 5000, 2000, 500)
    if st.button("Run Monte Carlo", type="primary"):
        try:
            mc = monte_carlo(company, assumptions, n=mc_n, seed=0, keep_samples=True)
        except ValueError as exc:
            st.error(str(exc))
        else:
            samples = pd.DataFrame({"value / share": mc.samples})
            hist = alt.Chart(samples).mark_bar(opacity=0.8).encode(
                x=alt.X("value / share:Q", bin=alt.Bin(maxbins=40)), y=alt.Y("count()", title="draws"))
            if price:
                hist = hist + alt.Chart(pd.DataFrame({"price": [price]})).mark_rule(
                    color="red", strokeDash=[4, 4]).encode(x="price:Q")
            st.altair_chart(hist, width="stretch")
            m1, m2, m3 = st.columns(3)
            m1.metric("Median value", f"{mc.median:,.2f}")
            m2.metric("90% range", f"{mc.p5:,.0f} – {mc.p95:,.0f}")
            m3.metric("P(value > price)",
                      f"{mc.prob_value_above_price:.0%}" if mc.prob_value_above_price is not None else "—")

# --------------------------------------------------------------------------- full report
with tab_report:
    st.caption("Generate the complete auditable markdown report (assumptions, all estimates, "
               "sensitivity, scenarios, Monte Carlo, reverse-DCF, warnings).")
    if st.button("Build full report"):
        report_md = render_report(company, assumptions, peer_companies, mc_n=2000, seed=0)
        st.download_button("⬇️ Download report (.md)", report_md,
                           file_name=f"{ticker}_valuation.md", mime="text/markdown")
        st.markdown(report_md)
