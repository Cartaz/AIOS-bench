#!/usr/bin/env python3
"""Generate a monthly expense report from a transaction CSV.

Usage:
    python tools/expense_report.py --input data/expenses.csv --output reports/monthly_expense_report.md

The script:
- Reads a CSV with columns: date, category, description, amount
- Skips malformed rows (e.g. missing amount) without guessing values
- Produces a Markdown monthly expense report grouped by month and category
- Writes the report to the --output path
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
    parser = argparse.ArgumentParser(
        description="Generate a monthly expense report from a transaction CSV."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input transaction CSV file.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to the output Markdown report file.",
    )
    return parser.parse_args()


def read_transactions(input_path: str) -> tuple[list[dict[str, Any]], list[int]]:
    """Read and validate transactions from CSV.

    Returns:
        A tuple of (valid_transactions, skipped_row_numbers).
        Rows with missing or non-numeric amounts are skipped without guessing.
    """
    path = Path(input_path)
    if not path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    valid_transactions: list[dict[str, Any]] = []
    skipped_rows: list[int] = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Validate required columns exist
        if reader.fieldnames is None:
            print("Error: CSV file is empty or has no header row.", file=sys.stderr)
            sys.exit(1)

        required_cols = {"date", "category", "description", "amount"}
        actual_cols = set(reader.fieldnames)
        missing_cols = required_cols - actual_cols
        if missing_cols:
            print(
                f"Error: CSV is missing required columns: {missing_cols}",
                file=sys.stderr,
            )
            sys.exit(1)

        for row_num, row in enumerate(reader, start=2):  # row 1 is the header
            date_str = row.get("date", "").strip()
            category = row.get("category", "").strip()
            description = row.get("description", "").strip()
            amount_str = row.get("amount", "").strip()

            # Skip rows with empty date, category, or description
            if not date_str or not category or not description:
                skipped_rows.append(row_num)
                continue

            # Skip rows with missing or non-numeric amounts — do NOT guess
            if not amount_str:
                skipped_rows.append(row_num)
                continue

            try:
                amount = float(amount_str)
            except ValueError:
                skipped_rows.append(row_num)
                continue

            # Validate date format
            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                skipped_rows.append(row_num)
                continue

            valid_transactions.append(
                {
                    "date": parsed_date,
                    "date_str": date_str,
                    "category": category,
                    "description": description,
                    "amount": amount,
                }
            )

    return valid_transactions, skipped_rows


def group_by_month(transactions: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Group transactions by (month, category)."""
    monthly: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for txn in transactions:
        month_key = txn["date"].strftime("%Y-%m")
        monthly[month_key][txn["category"]].append(txn)
    return dict(monthly)


def generate_report(
    transactions: list[dict[str, Any]],
    skipped_rows: list[int],
    valid_count: int,
) -> str:
    """Generate a Markdown monthly expense report."""
    lines: list[str] = []
    lines.append("# Monthly Expense Report")
    lines.append("")

    if not transactions:
        lines.append("*No valid transactions found.*")
        lines.append("")
        return "\n".join(lines)

    monthly = group_by_month(transactions)

    # Summary totals
    grand_total = sum(t["amount"] for t in transactions)

    # Grand total by category
    category_totals: dict[str, float] = defaultdict(float)
    for txn in transactions:
        category_totals[txn["category"]] += txn["amount"]

    lines.append("## Summary")
    lines.append("")
    lines.append(f"**Total transactions:** {valid_count}")
    lines.append(f"**Grand total:** ${grand_total:,.2f}")
    lines.append("")

    lines.append("### Total by Category")
    lines.append("")
    lines.append("| Category | Total |")
    lines.append("|----------|-------|")
    for cat in sorted(category_totals):
        lines.append(f"| {cat} | ${category_totals[cat]:,.2f} |")
    lines.append(f"| **Total** | **${grand_total:,.2f}** |")
    lines.append("")

    # Monthly breakdown
    lines.append("## Monthly Breakdown")
    lines.append("")

    for month_key in sorted(monthly.keys()):
        month_label = datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")
        month_total = sum(
            txn["amount"]
            for cats in monthly[month_key].values()
            for txn in cats
        )
        lines.append(f"### {month_label}")
        lines.append("")

        for category in sorted(monthly[month_key].keys()):
            month_total_cat = sum(txn["amount"] for txn in monthly[month_key][category])
            lines.append(f"#### {category}")
            lines.append("")
            lines.append("| Date | Description | Amount |")
            lines.append("|------|-------------|--------|")
            for txn in sorted(monthly[month_key][category], key=lambda t: t["date"]):
                lines.append(
                    f"| {txn['date_str']} | {txn['description']} | ${txn['amount']:,.2f} |"
                )
            lines.append(f"| | **{category} total** | **${month_total_cat:,.2f}** |")
            lines.append("")
        lines.append(f"**{month_label} total: ${month_total:,.2f}**")
        lines.append("")

    # Malformed rows notice
    if skipped_rows:
        lines.append("## Skipped Rows")
        lines.append("")
        lines.append(
            "The following rows were skipped due to missing or invalid data. "
            "No values were guessed or inferred."
        )
        lines.append("")
        lines.append(f"**Skipped row numbers (data rows):** {', '.join(str(r) for r in skipped_rows)}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    valid_transactions, skipped_rows = read_transactions(args.input)

    output_dir = Path(args.output).parent
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    report = generate_report(valid_transactions, skipped_rows, len(valid_transactions))

    Path(args.output).write_text(report + "\n", encoding="utf-8")
    print(f"Report written to {args.output}")
    print(f"  Valid transactions: {len(valid_transactions)}")
    print(f"  Skipped rows: {len(skipped_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
