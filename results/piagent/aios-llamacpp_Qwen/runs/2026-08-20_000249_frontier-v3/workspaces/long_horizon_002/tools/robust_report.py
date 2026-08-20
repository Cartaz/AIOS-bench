#!/usr/bin/env python3
"""Robust report CLI: reads a CSV and produces a plain-text report.

Handles edge cases gracefully:
  - Empty datasets produce an empty but valid report
  - Missing input files exit with non-zero code
  - Non-numeric values are skipped silently

Usage:
    python tools/robust_report.py --input data/sales.csv --output report.txt
    python tools/robust_report.py --input data/expenses_empty.csv --output empty.txt
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Robust plain-text report from CSV")
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--output", required=True, help="Path to output text report")
    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.is_file():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with input_file.open(newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    lines = ["Robust Report", "=============", ""]
    lines.append(f"Input: {args.input}")
    lines.append(f"Rows: {len(rows)}")
    lines.append(f"Columns: {', '.join(fieldnames)}")
    lines.append("")

    for col in fieldnames:
        values = [row.get(col, "") for row in rows]
        nums = [to_float(v) for v in values if _is_numeric(v)]
        if nums:
            s = round(sum(nums), 4)
            m = round(s / len(nums), 4)
            lines.append(f"  {col}: count={len(nums)}, sum={s}, mean={m}, min={min(nums)}, max={max(nums)}")
        else:
            lines.append(f"  {col}: no numeric values")

    lines.append("")
    lines.append("--- End of report ---")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
