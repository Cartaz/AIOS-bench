#!/usr/bin/env python3
"""Step 1: Read a CSV dataset and produce a summary JSON.

Reads a CSV file with numeric columns, computes:
  - row_count: number of data rows
  - column_names: list of column names
  - for each numeric column: mean, min, max, sum, count of non-null values

Usage:
    python tools/step1_summary.py --input data/sales.csv --output reports/summary.json

If the input file does not exist, exits with code 1.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def is_numeric(value: str) -> bool:
    """Return True if the string can be interpreted as a number."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def to_float(value: str) -> float | None:
    """Convert to float, return None for empty/non-numeric values."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def compute_column_stats(values: list[str]) -> dict:
    """Compute statistics for a single column."""
    nums = [to_float(v) for v in values]
    valid = [n for n in nums if n is not None]
    if not valid:
        return {"count": 0, "sum": None, "mean": None, "min": None, "max": None}
    return {
        "count": len(valid),
        "sum": round(sum(valid), 4),
        "mean": round(sum(valid) / len(valid), 4),
        "min": min(valid),
        "max": max(valid),
    }


def build_summary(input_path: str, output_path: str) -> None:
    """Read CSV, build summary dict, write JSON."""
    path = Path(input_path)
    if not path.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    # Determine numeric columns
    summary = {
        "row_count": len(rows),
        "column_names": list(fieldnames),
        "columns": {},
    }

    for col in fieldnames:
        values = [row.get(col, "") for row in rows]
        stats = compute_column_stats(values)
        summary["columns"][col] = stats

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Summary written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 1: Generate summary JSON from CSV")
    parser.add_argument("--input", required=True, help="Path to input CSV file")
    parser.add_argument("--output", required=True, help="Path to output summary JSON")
    args = parser.parse_args()
    build_summary(args.input, args.output)


if __name__ == "__main__":
    main()
