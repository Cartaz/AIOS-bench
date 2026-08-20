"""CSV parsing module – reads and converts CSV rows."""

from __future__ import annotations

import csv
from pathlib import Path


def read_csv(path: str | Path) -> list[dict[str, str]]:
    """Read a CSV file and return a list of row dicts (all values as strings)."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Input file not found: {p}")
    with p.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def parse_numeric(value: str) -> float | None:
    """Convert a string to float, returning None for blanks / unparseable."""
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "":
        return None
    try:
        return float(stripped)
    except ValueError:
        return None
