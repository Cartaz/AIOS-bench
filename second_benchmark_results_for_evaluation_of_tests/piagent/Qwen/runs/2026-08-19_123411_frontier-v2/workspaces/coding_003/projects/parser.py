"""Parsing module – turns raw input into a list of numeric values.

Accepts:
  - A list of raw values (ints, floats, strings representing numbers)
  - A file path pointing to a CSV with an 'amount' column
  - A comma-separated string of values

The caller passes raw_input to parse_values() and gets back a list of
floats (or None on failure).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any


def _coerce_value(raw: Any) -> float | None:
    """Try to turn a single raw value into a float.

    Returns None when the value cannot be interpreted as a number.
    """
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped == "":
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def parse_values(raw_input: list[Any]) -> list[float] | None:
    """Parse a list of raw values into floats.

    - Skips items that cannot be converted.
    - Returns an empty list if *all* items are invalid (still a valid,
      non-crashing result rather than None).

    Returns:
        A list of floats on success.
        None only when raw_input itself is not a list.
    """
    if not isinstance(raw_input, (list, tuple)):
        return None

    results: list[float] = []
    for item in raw_input:
        converted = _coerce_value(item)
        if converted is not None:
            results.append(converted)
        # Invalid items are silently skipped so the tool does not crash.

    return results


def parse_csv(filepath: str) -> list[float] | None:
    """Parse numeric values from the *amount* column of a CSV file.

    Returns None when the file does not exist or has no valid rows.
    """
    path = Path(filepath)
    if not path.is_file():
        return None

    results: list[float] = []
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None or "amount" not in reader.fieldnames:
                return None
            for row in reader:
                val = _coerce_value(row["amount"])
                if val is not None:
                    results.append(val)
    except (OSError, csv.Error):
        return None

    return results if results else None
