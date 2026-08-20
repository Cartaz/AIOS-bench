"""Reporting tool – modularised into parsing, validation, and reporting."""

from __future__ import annotations

from .parser import read_csv, parse_numeric  # noqa: F401
from .validator import validate_rows, aggregate  # noqa: F401
from .reporter import generate_html_report, generate_text_report  # noqa: F401
