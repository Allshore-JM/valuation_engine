"""CLI tests (offline, via typer's CliRunner) + the pipeline override path."""
from __future__ import annotations

from typer.testing import CliRunner

from valuation_engine.cli import app
from valuation_engine.data import FixtureProvider
from valuation_engine.pipeline import run_valuation

runner = CliRunner()


def test_cli_offline_valuation_with_peers():
    result = runner.invoke(
        app, ["AAPL", "--offline", "--no-monte-carlo", "--peers", "MSFT,NVDA,ORCL,CRM,AVGO"]
    )
    assert result.exit_code == 0, result.output
    assert "# Valuation report" in result.output
    assert "Value estimates vs price" in result.output


def test_cli_writes_html_to_file(tmp_path):
    out = tmp_path / "report.html"
    result = runner.invoke(
        app, ["KO", "--offline", "--no-monte-carlo", "--fmt", "html", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_cli_override_changes_assumptions(tmp_path):
    out = tmp_path / "r.md"
    result = runner.invoke(
        app, ["AAPL", "--offline", "--no-monte-carlo", "--wacc", "0.20", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert "| WACC | 20.0% |" in out.read_text(encoding="utf-8")


def test_cli_unknown_ticker_offline_exits_nonzero():
    result = runner.invoke(app, ["ZZZZ", "--offline"])
    assert result.exit_code == 1


def test_run_valuation_direct_override():
    run = run_valuation("AAPL", FixtureProvider(), overrides={"wacc": 0.20}, run_monte_carlo=False)
    assert run.assumptions.cost_of_capital == 0.20
