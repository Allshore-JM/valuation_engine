"""Minimal HTML wrapper around the markdown report.

A lightweight, dependency-free embedding (the markdown is shown in a styled <pre>). A
richer markdown->HTML conversion (and PDF) is deferred — it needs an extra dependency.
"""
from __future__ import annotations

import html as _html


def render_html(markdown_text: str, title: str = "Valuation report") -> str:
    body = _html.escape(markdown_text)
    return (
        "<!doctype html>\n<html lang='en'>\n<head>\n<meta charset='utf-8'>\n"
        f"<title>{_html.escape(title)}</title>\n"
        "<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;"
        "margin:2rem auto;padding:0 1rem;line-height:1.5}"
        "pre{white-space:pre-wrap;word-wrap:break-word}</style>\n</head>\n"
        f"<body>\n<pre>{body}</pre>\n</body>\n</html>\n"
    )
