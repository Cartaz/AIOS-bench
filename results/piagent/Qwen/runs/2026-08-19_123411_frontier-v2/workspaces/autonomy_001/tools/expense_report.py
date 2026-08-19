#!/usr/bin/env python3
"""
expense_report.py — Reusable monthly expense report generator.

Reads authoritative transaction data from data/expenses.csv,
produces a monthly expense report saved as reports/monthly_expense_report.md.

Usage:
    python tools/expense_report.py [--workspace PATH]
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime


def load_expenses(path: str) -> list[dict]:
    """Load and validate expense records from a CSV file."""
    if not os.path.isfile(path):
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        # Validate expected columns
        required = {"date", "category", "description", "amount"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            print(
                f"Error: {path} must contain columns: {', '.join(sorted(required))}",
                file=sys.stderr,
            )
            sys.exit(1)

        rows: list[dict] = []
        for lineno, row in enumerate(reader, start=2):  # header is line 1
            try:
                row["amount"] = float(row["amount"])
            except ValueError:
                print(
                    f"Warning: skipping row {lineno} — non-numeric amount: {row['amount']}",
                    file=sys.stderr,
                )
                continue
            # Validate date format YYYY-MM-DD
            try:
                datetime.strptime(row["date"], "%Y-%m-%d")
            except ValueError:
                print(
                    f"Warning: skipping row {lineno} — invalid date: {row['date']}",
                    file=sys.stderr,
                )
                continue
            rows.append(row)

    return rows


def aggregate(rows: list[dict]) -> dict:
    """Aggregate expense rows by month and category."""
    by_month: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "total": 0.0, "items": []}
    )
    by_category: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "total": 0.0, "items": []}
    )

    for r in rows:
        amt = r["amount"]
        month = r["date"][:7]  # "YYYY-MM"

        by_month[month]["count"] += 1
        by_month[month]["total"] += amt
        by_month[month]["items"].append(r)

        by_category[r["category"]]["count"] += 1
        by_category[r["category"]]["total"] += amt
        by_category[r["category"]]["items"].append(r)

    return {
        "total": sum(r["amount"] for r in rows),
        "by_month": dict(by_month),
        "by_category": dict(by_category),
    }


def validate(aggregated: dict, rows: list[dict]) -> None:
    """Cross-check totals and raise on inconsistency."""
    row_sum = sum(r["amount"] for r in rows)
    cat_sum = sum(d["total"] for d in aggregated["by_category"].values())
    month_sum = sum(d["total"] for d in aggregated["by_month"].values())
    grand = aggregated["total"]

    checks = [
        ("row sum", row_sum, grand),
        ("category subtotal", cat_sum, grand),
        ("monthly subtotal", month_sum, grand),
    ]
    for label, actual, expected in checks:
        if round(actual, 2) != round(expected, 2):
            raise AssertionError(
                f"Validation failed: {label} ({actual:.2f}) != total ({expected:.2f})"
            )


def render_report(aggregated: dict, rows: list[dict]) -> str:
    """Render a Markdown monthly expense report."""
    lines: list[str] = []
    total = aggregated["total"]
    n = len(rows)

    # Find the single month (or list all months)
    months = sorted(aggregated["by_month"].keys())

    lines.append("# Monthly Expense Report")
    lines.append("")

    if len(months) == 1:
        lines.append(f"## {months[0]}")
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric            | Value      |")
    lines.append("|-------------------|------------|")
    lines.append(f"| Total Expenses    | ${total:.2f}     |")
    lines.append(f"| Number of Items   | {n}          |")
    if len(months) == 1:
        lines.append(
            f"| Report Period     | {months[0]}-01 to {months[0]}-31 |"
        )
    lines.append("")

    # Monthly table
    lines.append("## Monthly Totals")
    lines.append("")
    lines.append("| Month     | Transactions | Total   |")
    lines.append("|-----------|-------------|---------|")
    for m in months:
        d = aggregated["by_month"][m]
        lines.append(f"| {m}   | {d['count']}           | ${d['total']:.2f}  |")
    lines.append("")

    # Category breakdown
    lines.append("## Expense Breakdown by Category")
    lines.append("")
    lines.append("| Category | Count | Total   | % of Total |")
    lines.append("|----------|-------|---------|------------|")
    for cat in sorted(aggregated["by_category"]):
        d = aggregated["by_category"][cat]
        pct = (d["total"] / total * 100) if total else 0
        lines.append(
            f"| {cat:<8} | {d['count']}     | ${d['total']:.2f}  | {pct:8.2f} %    |"
        )
    lines.append("")

    # Detail table (sorted by date)
    sorted_rows = sorted(rows, key=lambda r: r["date"])
    lines.append("## Detailed Transactions")
    lines.append("")
    lines.append("| Date       | Category | Description      | Amount  |")
    lines.append("|------------|----------|------------------|---------|")
    for r in sorted_rows:
        lines.append(
            f"| {r['date']} | {r['category']:<8} | {r['description']:<14} | ${r['amount']:.2f}  |"
        )
    lines.append("")

    # Validation section
    lines.append("## Validation")
    lines.append("")
    lines.append(f"- Source file: `data/expenses.csv`")
    lines.append(f"- Row count: {n}")

    if n > 0:
        amt_parts = " + ".join(f"${r['amount']:.2f}" for r in sorted_rows)
        lines.append(f"- Sum of individual amounts: {amt_parts} = **${total:.2f}** ✅")

    if aggregated["by_category"]:
        cat_parts = " + ".join(
            f"${d['total']:.2f}" for d in sorted(aggregated["by_category"].values(), key=lambda d: d['total'], reverse=True)
        )
        lines.append(f"- Category subtotal check: {cat_parts} = **${total:.2f}** ✅")

    if aggregated["by_month"]:
        month_parts = " + ".join(
            f"${d['total']:.2f}" for d in sorted(aggregated["by_month"].values(), key=lambda d: d['total'], reverse=True)
        )
        lines.append(f"- Monthly subtotal check: {month_parts} = **${total:.2f}** ✅")

    lines.append("- All totals reconcile — report is consistent.")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a monthly expense report from data/expenses.csv."
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Path to the workspace root (defaults to the script's parent directory).",
    )
    args = parser.parse_args()

    # Determine workspace root
    if args.workspace:
        workspace = args.workspace
    else:
        workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Paths
    data_path = os.path.join(workspace, "data", "expenses.csv")
    report_path = os.path.join(workspace, "reports", "monthly_expense_report.md")

    # Load and aggregate
    rows = load_expenses(data_path)
    aggregated = aggregate(rows)

    # Validate
    validate(aggregated, rows)

    # Render and save
    report = render_report(aggregated, rows)

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as fh:
        fh.write(report)

    print(f"Report written to: {report_path}")
    print(f"Total expenses: ${aggregated['total']:.2f}")


if __name__ == "__main__":
    main()
