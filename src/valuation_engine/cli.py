"""`valuate` — command-line front end for the valuation engine.

    valuate AAPL --peers MSFT,NVDA,ORCL --out report.md

Outputs are model estimates, not investment advice.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from valuation_engine.data import FixtureProvider, YFinanceProvider
from valuation_engine.pipeline import run_valuation
from valuation_engine.report import render_html

app = typer.Typer(
    add_completion=False,
    help="Estimate a company's intrinsic value and compare it to price. NOT investment advice.",
)


@app.command()
def valuate(
    ticker: str = typer.Argument(..., help="Ticker symbol, e.g. AAPL"),
    peers: Optional[str] = typer.Option(None, help="Comma-separated peer tickers for relative valuation"),
    out: Optional[Path] = typer.Option(None, help="Write the report to this file instead of stdout"),
    fmt: str = typer.Option("markdown", help="Output format: markdown | html"),
    offline: bool = typer.Option(False, help="Use committed fixtures instead of live yfinance"),
    rf: Optional[float] = typer.Option(None, help="Override risk-free rate (decimal, e.g. 0.043)"),
    erp: Optional[float] = typer.Option(None, help="Override equity risk premium (decimal)"),
    tax: Optional[float] = typer.Option(None, help="Override marginal tax rate (decimal)"),
    wacc: Optional[float] = typer.Option(None, help="Override WACC (decimal)"),
    ke: Optional[float] = typer.Option(None, help="Override cost of equity (decimal)"),
    beta: Optional[float] = typer.Option(None, help="Override beta"),
    high_growth: Optional[float] = typer.Option(None, help="Override high-growth phase rate (decimal)"),
    stable_growth: Optional[float] = typer.Option(None, help="Override stable growth (decimal)"),
    stable_roc: Optional[float] = typer.Option(None, help="Override stable ROC (decimal)"),
    no_monte_carlo: bool = typer.Option(False, "--no-monte-carlo", help="Skip the Monte Carlo section"),
    mc_n: int = typer.Option(2000, help="Monte Carlo iterations"),
    seed: int = typer.Option(0, help="Monte Carlo seed (for reproducibility)"),
    margin_of_safety: Optional[float] = typer.Option(
        None, help="Margin-of-safety threshold (decimal), e.g. 0.2 for 20%"
    ),
) -> None:
    provider = FixtureProvider() if offline else YFinanceProvider()
    overrides = {
        k: v
        for k, v in dict(
            rf=rf, erp=erp, tax=tax, wacc=wacc, ke=ke, beta=beta,
            high_growth=high_growth, stable_growth=stable_growth, stable_roc=stable_roc,
        ).items()
        if v is not None
    }
    peer_list = [p.strip().upper() for p in peers.split(",")] if peers else None

    try:
        run = run_valuation(
            ticker.upper(), provider,
            peer_tickers=peer_list, overrides=overrides,
            run_monte_carlo=not no_monte_carlo, mc_n=mc_n, seed=seed,
            margin_of_safety_threshold=margin_of_safety,
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure cleanly to the user
        typer.secho(f"error valuing {ticker!r}: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    content = run.report_markdown
    if fmt == "html":
        content = render_html(run.report_markdown, title=run.ticker)
    if out:
        out.write_text(content, encoding="utf-8")
        typer.secho(f"wrote {fmt} report to {out}", fg=typer.colors.GREEN, err=True)
    else:
        typer.echo(content)

    tri = run.triangulation
    typer.secho(
        f"{run.ticker}: price={run.price} · intrinsic median={tri.intrinsic_median} · "
        f"margin of safety={run.margin_of_safety}",
        fg=typer.colors.CYAN, err=True,
    )
    if run.meets_threshold is not None:
        verdict = "MEETS" if run.meets_threshold else "below"
        typer.secho(
            f"margin of safety {verdict} threshold {margin_of_safety}",
            fg=(typer.colors.GREEN if run.meets_threshold else typer.colors.YELLOW), err=True,
        )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
