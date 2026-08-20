#!/usr/bin/env python3
"""Generic report CLI — wraps the expense_report module to produce HTML output.

Usage:
    python tools/report_cli.py --input <csv> --output <html>

Supports any CSV with: date, category, description, amount
OR: date, product, units, revenue
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a report from a CSV.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def normalize_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[int]]:
    """Normalize rows into a common format.  Skips malformed rows."""
    valid: list[dict[str, Any]] = []
    skipped: list[int] = []

    # Detect schema
    if rows and "amount" in rows[0]:
        # expenses schema: date, category, description, amount
        for i, row in enumerate(rows, start=2):
            date_s = row.get("date", "").strip()
            cat = row.get("category", "").strip()
            desc = row.get("description", "").strip()
            amt_s = row.get("amount", "").strip()

            if not date_s or not cat or not desc or not amt_s:
                skipped.append(i)
                continue
            try:
                dt = datetime.strptime(date_s, "%Y-%m-%d")
            except ValueError:
                skipped.append(i)
                continue
            try:
                amt = float(amt_s)
            except ValueError:
                skipped.append(i)
                continue

            valid.append({"date": dt, "date_str": date_s, "category": cat,
                          "description": desc, "amount": amt, "units": "N/A"})
    elif rows and "revenue" in rows[0]:
        # sales schema: date, product, units, revenue
        for i, row in enumerate(rows, start=2):
            date_s = row.get("date", "").strip()
            product = row.get("product", "").strip()
            units_s = row.get("units", "").strip()
            rev_s = row.get("revenue", "").strip()

            if not date_s or not product or not units_s or not rev_s:
                skipped.append(i)
                continue
            try:
                dt = datetime.strptime(date_s, "%Y-%m-%d")
            except ValueError:
                skipped.append(i)
                continue
            try:
                rev = float(rev_s)
                units = int(units_s)
            except ValueError:
                skipped.append(i)
                continue

            valid.append({"date": dt, "date_str": date_s, "category": product,
                          "description": f"{product} (x{units})", "amount": rev, "units": units})
    else:
        # Unknown schema — no data rows to produce
        pass

    return valid, skipped


def html_report(rows: list[dict[str, Any]], skipped: list[int], n_valid: int) -> str:
    """Produce an HTML report string."""
    grand = sum(r["amount"] for r in rows)

    lines: list[str] = []
    lines.append("<!DOCTYPE html>")
    lines.append("<html><head><title>Expense Report</title>")
    lines.append("<style>table{border-collapse:collapse}th,td{border:1px solid #999;padding:4px 8px;text-align:left}</style>")
    lines.append("</head><body>")
    lines.append(f"<h1>Monthly Expense Report</h1>")
    lines.append(f"<p><strong>Total transactions:</strong> {n_valid}  |  <strong>Grand total:</strong> ${grand:,.2f}</p>")

    cats: dict[str, float] = defaultdict(float)
    for r in rows:
        cats[r["category"]] += r["amount"]

    lines.append("<h2>By Category</h2>")
    lines.append("<table><tr><th>Category</th><th>Total</th></tr>")
    for c in sorted(cats):
        lines.append(f"<tr><td>{c}</td><td>${cats[c]:,.2f}</td></tr>")
    lines.append(f"<tr><td><strong>Total</strong></td><td><strong>${grand:,.2f}</strong></td></tr>")
    lines.append("</table>")

    if skipped:
        lines.append(f"<h2>Skipped Rows: {', '.join(str(s) for s in skipped)}</h2>")

    lines.append("</body></html>")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    rows = read_csv(args.input)
    valid, skipped = normalize_rows(rows)
    output_dir = Path(args.output).parent
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    html = html_report(valid, skipped, len(valid))
    Path(args.output).write_text(html + "\n", encoding="utf-8")
    print(f"Report written to {args.output}  ({len(valid)} valid, {len(skipped)} skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
