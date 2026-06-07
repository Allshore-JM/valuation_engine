"""Streamlit web UI for the equity valuation engine.

Run locally:   streamlit run streamlit_app.py
Deployed on:   Streamlit Community Cloud (auto-redeploys from the GitHub repo on push)

The engine code is untouched; this file is just a thin UI on top of it. All the
plain-English explanations live in help_text.py.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Make src/ (the package) and this folder (help_text.py) importable, whether or not the
# package is pip-installed — e.g. on Streamlit Cloud.
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import help_text as txt  # noqa: E402

# Streamlit Cloud can keep an older copy of an imported module across a redeploy, so a
# newly-added constant would raise AttributeError. Reloading guarantees edits take effect.
importlib.reload(txt)

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


def _suggest_peers(source: str, ticker: str) -> list[str]:
    provider = FixtureProvider() if source == OFFLINE else YFinanceProvider()
    try:
        with st.spinner("Finding comparable companies…"):
            return provider.suggest_peers(ticker)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Auto-suggest failed: {exc}")
        return []


def peer_selector(source: str, ticker: str, available: list[str]) -> list[str]:
    """Editable peer list with an 'Auto-suggest peers' button. Returns the chosen tickers."""
    state_key = f"peers::{source}::{ticker}"
    suggest_clicked = st.button("🔮 Auto-suggest peers", help=txt.AUTO_PEERS, use_container_width=True)

    if source == OFFLINE:
        options = [t for t in available if t != ticker]
        if state_key not in st.session_state:
            st.session_state[state_key] = [p for p in DEFAULT_PEERS.get(ticker, []) if p in options]
        if suggest_clicked:
            picks = [s for s in _suggest_peers(source, ticker) if s in options]
            if picks:
                st.session_state[state_key] = picks
            else:
                st.info("No peers with bundled data — switch to **Live** to value other tickers.")
        return st.multiselect("Peers (relative valuation)", options, key=state_key, help=txt.PEERS)

    # live mode — free-text tickers
    if state_key not in st.session_state:
        st.session_state[state_key] = ",".join(DEFAULT_PEERS.get(ticker, []))
    if suggest_clicked:
        picks = _suggest_peers(source, ticker)
        if picks:
            st.session_state[state_key] = ",".join(picks)
        else:
            st.warning("Couldn't find peers automatically — enter some manually.")
    raw = st.text_input("Peers (comma-separated)", key=state_key, help=txt.PEERS)
    return [p.strip().upper() for p in raw.split(",") if p.strip()]


# ----------------------------------------------------------------------------- header
st.title("📈 Equity Valuation Engine")
st.caption(
    "Estimate what a company is *worth* (intrinsic value) and compare it to what it *costs* "
    "(market price) — built on Damodaran's *Investment Valuation*."
)
st.warning(
    "**Not investment advice.** Every number is a model estimate driven by the assumptions in "
    "the sidebar. Garbage in, garbage out — change an assumption and the answer changes."
)
with st.expander("📖 **New here? How this tool works — start here**", expanded=False):
    st.markdown(txt.INTRO)
for _w in all_staleness_warnings():
    st.info(_w, icon="🕓")

# --------------------------------------------------------------------- sidebar: inputs
with st.sidebar:
    st.header("1 · Company")
    source = st.radio("Data source", [OFFLINE, LIVE], index=0, help=txt.DATA_SOURCE)
    available = fixture_tickers() if source == OFFLINE else []
    if source == OFFLINE:
        ticker = st.selectbox("Ticker", [t for t in ("AAPL", "KO") if t in available] or available,
                              help=txt.TICKER)
    else:
        ticker = (st.text_input("Ticker", value="AAPL", help=txt.TICKER) or "").strip().upper()
    peers = peer_selector(source, ticker, available) if ticker else []

if not ticker:
    st.stop()

try:
    company, peer_companies, base = load_data(source, ticker, tuple(peers))
except Exception as exc:  # noqa: BLE001
    st.error(f"Couldn't load **{ticker}**: {exc}")
    st.stop()

with st.sidebar:
    st.header("2 · Assumptions")
    st.caption("Each knob starts at a value estimated from the firm's own history. "
               "Hover the **?** on any slider for what it means and how it moves the answer.")
    rf = float(base.risk_free_rate or 0.043)
    wacc = st.slider("WACC — FCFF discount rate", 0.03, 0.20, float(base.cost_of_capital or 0.09),
                     0.001, format="%.3f", help=txt.WACC)
    ke = st.slider("Cost of equity — FCFE/DDM discount rate", 0.03, 0.25, float(base.cost_of_equity or 0.09),
                   0.001, format="%.3f", help=txt.KE)
    high_growth = st.slider("High-growth rate (first 5 years)", -0.05, 0.40, float(base.phases[0].growth_rate or 0.08),
                            0.005, format="%.3f", help=txt.HIGH_GROWTH)
    sg_max = max(0.001, min(rf, wacc - 0.001, ke - 0.001))
    stable_growth = st.slider("Stable (perpetuity) growth", 0.0, float(sg_max),
                              float(min(base.stable_growth_rate or 0.02, sg_max)), 0.001, format="%.3f",
                              help=txt.STABLE_GROWTH)
    tax = st.slider("Tax rate", 0.0, 0.40, float(base.marginal_tax_rate or 0.21), 0.01, format="%.2f", help=txt.TAX)
    with st.expander("Advanced"):
        stable_roc = st.slider("Stable return on capital", 0.03, 0.30,
                               float(base.stable_return_on_capital or base.cost_of_capital or 0.09),
                               0.005, format="%.3f", help=txt.STABLE_ROC)
        st.caption("These three feed the suggested WACC and cost of equity above:")
        st.metric("Risk-free rate", f"{rf:.2%}", help=txt.RF)
        st.metric("Equity risk premium", f"{float(base.equity_risk_premium or 0):.2%}", help=txt.ERP)
        st.metric("Beta", f"{float(base.beta or 0):.2f}", help=txt.BETA)

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
c1.metric("Market price", f"{price:,.2f}" if price else "—", help=txt.M_PRICE)
c2.metric("Intrinsic median", f"{tri.intrinsic_median:,.2f}" if tri.intrinsic_median else "—", help=txt.M_INTRINSIC)
c3.metric("Relative median", f"{tri.relative_median:,.2f}" if tri.relative_median else "—", help=txt.M_RELATIVE)
c4.metric("Margin of safety", f"{tri.margin_of_safety:.1%}" if tri.margin_of_safety is not None else "—",
          help=txt.M_MOS)

tab_summary, tab_sens, tab_mc, tab_report = st.tabs(
    ["Summary", "Sensitivity & scenarios", "Monte Carlo", "Full report"]
)

# --------------------------------------------------------------------------- summary
with tab_summary:
    st.caption("Each method estimates value per share a different way. "
               "The red dashed line is the current market price.")
    with st.expander("ℹ️ What do FCFF, FCFE, DDM and the relative multiples mean?"):
        st.markdown(txt.METHODS)
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
    st.altair_chart(chart, use_container_width=True)
    st.dataframe(
        est_df, hide_index=True, use_container_width=True,
        column_config={
            "value / share": st.column_config.NumberColumn(format="%.2f", help="Estimated value of one share by this method."),
            "upside vs price": st.column_config.NumberColumn(format="percent", help=txt.UPSIDE),
        },
    )
    if implied:
        st.info(
            f"**Reverse DCF —** the current price implies a high-growth-phase rate of "
            f"**{implied.implied_phase_growth:.1%}**, vs your assumed **{high_growth:.1%}**."
            + (f"  _{implied.note}_" if implied.note else ""),
            icon="🔎",
        )
        st.caption(txt.REVERSE_DCF)

# ------------------------------------------------------------ sensitivity & scenarios
with tab_sens:
    st.markdown("**Sensitivity — one input at a time (FCFF value / share)**")
    st.caption(txt.SENSITIVITY)
    sdf = pd.DataFrame([{"input": b.input, "value @ low": b.low_value,
                         "value @ high": b.high_value, "swing": b.swing} for b in bars])
    st.altair_chart(
        alt.Chart(sdf).mark_bar().encode(
            x=alt.X("swing:Q", title="value swing"),
            y=alt.Y("input:N", sort="-x"),
            tooltip=[c for c in sdf.columns]),
        use_container_width=True,
    )
    st.dataframe(sdf, hide_index=True, use_container_width=True,
                 column_config={c: st.column_config.NumberColumn(format="%.2f")
                                for c in ("value @ low", "value @ high", "swing")})
    st.markdown("**Scenarios (FCFF)**")
    st.caption(txt.SCENARIOS)
    scen_df = pd.DataFrame([{"scenario": s.name, "value / share": s.value_per_share,
                             "discount": s.discount_rate, "stable g": s.stable_growth_rate,
                             "phase g": s.phase_growth} for s in scenarios])
    st.dataframe(scen_df, hide_index=True, use_container_width=True, column_config={
        "value / share": st.column_config.NumberColumn(format="%.2f"),
        "discount": st.column_config.NumberColumn(format="percent"),
        "stable g": st.column_config.NumberColumn(format="percent"),
        "phase g": st.column_config.NumberColumn(format="percent"),
    })

# --------------------------------------------------------------------------- monte carlo
with tab_mc:
    st.caption(txt.MONTE_CARLO)
    mc_n = st.slider("Iterations", 500, 5000, 2000, 500, help=txt.MC_ITER)
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
            st.altair_chart(hist, use_container_width=True)
            m1, m2, m3 = st.columns(3)
            m1.metric("Median value", f"{mc.median:,.2f}",
                      help="The middle outcome across all simulations.")
            m2.metric("90% range", f"{mc.p5:,.0f} – {mc.p95:,.0f}",
                      help="5th to 95th percentile — 90% of simulations land in this band.")
            m3.metric("P(value > price)",
                      f"{mc.prob_value_above_price:.0%}" if mc.prob_value_above_price is not None else "—",
                      help="Share of simulations in which the stock looks undervalued.")

# --------------------------------------------------------------------------- full report
with tab_report:
    st.caption("Generate the complete, auditable markdown report — every assumption, all "
               "estimates, sensitivity, scenarios, Monte Carlo, reverse-DCF and warnings.")
    if st.button("Build full report"):
        report_md = render_report(company, assumptions, peer_companies, mc_n=2000, seed=0)
        st.download_button("⬇️ Download report (.md)", report_md,
                           file_name=f"{ticker}_valuation.md", mime="text/markdown")
        st.markdown(report_md)

# --------------------------------------------------------------------------- glossary
with st.expander("📚 Glossary — plain-English definitions"):
    st.markdown(txt.GLOSSARY)
