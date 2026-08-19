#!/usr/bin/env python3
"""Generate a monthly sales summary from data/sales.csv.

Follows the current procedure in procedures/current.md:
  1. Export the monthly sales CSV.
  2. Validate the header and numeric fields.
  3. Calculate total revenue and units.
  4. Save the summary as reports/monthly-sales.md.
  5. (Review is manual — no further automation needed.)
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path


def validate_row(row: dict, field: str) -> float:
    """Return a numeric value or raise on bad data."""
    try:
        return float(row[field])
    except (ValueError, TypeError):
        raise ValueError(f"non-numeric value for '{field}': {row[field]!r}")


def load_sales(csv_path: Path) -> list[dict]:
    """Read and validate the sales CSV."""
    if not csv_path.is_file():
        print(f"Error: {csv_path} not found.", file=sys.stderr)
        sys.exit(1)

    rows: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        expected = {"date", "product", "units", "revenue"}
        if not expected.issubset(set(reader.fieldnames or [])):
            print(
                f"Error: expected headers {expected}, got {reader.fieldnames}",
                file=sys.stderr,
            )
            sys.exit(1)
        for row in reader:
            # Validate numeric fields
            validate_row(row, "units")
            validate_row(row, "revenue")
            rows.append(row)
    return rows


def summarize(rows: list[dict]) -> dict:
    """Return aggregated stats."""
    total_units = sum(float(r["units"]) for r in rows)
    total_revenue = sum(validate_row(r, "revenue") for r in rows)
    return {
        "total_units": total_units,
        "total_revenue": total_revenue,
        "row_count": len(rows),
    }


def save_summary(stats: dict, csv_path: Path, output_path: Path) -> None:
    """Write a Markdown summary report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    month = csv_path.stem  # e.g. 'sales' → not a date; use file name
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write(f"# Monthly Sales Summary\n\n")
        fh.write(f"Source: `{csv_path.name}`\n\n")
        fh.write(f"| Metric        | Value  |\n")
        fh.write(f"|---------------|--------|\n")
        fh.write(f"| Total Units   | {stats['total_units']:.0f}   |\n")
        fh.write(f"| Total Revenue | {stats['total_revenue']:.2f} |\n")
        fh.write(f"| Transactions  | {stats['row_count']}   |\n")
    print(f"Summary saved to {output_path}")


def main() -> None:
    workspace = Path(__file__).resolve().parent.parent  # workspace root
    csv_path = workspace / "data" / "sales.csv"
    output_path = workspace / "reports" / "monthly-sales.md"

    rows = load_sales(csv_path)
    stats = summarize(rows)
    save_summary(stats, csv_path, output_path)


if __name__ == "__main__":
    main()
