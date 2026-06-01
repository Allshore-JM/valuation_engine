"""Report renderers: markdown (full report) and a minimal HTML wrapper.

A single human-readable report listing every assumption, all value estimates,
over/under-valuation, sensitivity / scenarios / Monte Carlo, and the warnings.
"""
from valuation_engine.report.html import render_html
from valuation_engine.report.markdown import render_report

__all__ = ["render_html", "render_report"]
