"""Validation module – checks row data and reports issues."""

from __future__ import annotations

from .parser import parse_numeric


def validate_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """Validate each row and return cleaned rows with numeric fields.

    Returns a list of dicts where any parseable numeric column has been
    converted to float (or None if blank / unparseable).
    """
    cleaned: list[dict[str, object]] = []
    for row in rows:
        new_row: dict[str, object] = {}
        for key, value in row.items():
            num = parse_numeric(value)
            new_row[key] = num if num is not None else value
        cleaned.append(new_row)
    return cleaned


def aggregate(reports: list[dict[str, object]], numeric_cols: list[str]) -> dict[str, float]:
    """Sum numeric columns across all rows, skipping None / non-numeric."""
    totals: dict[str, float] = {col: 0.0 for col in numeric_cols}
    for row in reports:
        for col in numeric_cols:
            val = row.get(col)
            if isinstance(val, (int, float)) and not (isinstance(val, float) and val != val):  # skip NaN
                totals[col] += val
    return totals
