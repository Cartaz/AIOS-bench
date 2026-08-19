#!/usr/bin/env python3
"""Generate a monthly expense report from a CSV of transactions.

Usage:
    python tools/expense_report.py --input data/expenses.csv --output reports/monthly_expense_report.md
"""

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime


def parse_transactions(input_path):
    """Parse expense CSV and return (valid_rows, malformed_rows).

    Valid row: date, category, description, amount (amount must be a valid number).
    Malformed rows are skipped without guessing their values.
    """
    valid = []
    malformed = []

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Validate expected columns
        if reader.fieldnames != ["date", "category", "description", "amount"]:
            print(
                f"Error: expected columns date,category,description,amount but got {reader.fieldnames}",
                file=sys.stderr,
            )
            sys.exit(1)

        for line_no, row in enumerate(reader, start=2):
            date_str = row.get("date", "").strip()
            category = row.get("category", "").strip()
            description = row.get("description", "").strip()
            amount_str = row.get("amount", "").strip()

            # Validate all required fields are present and non-empty
            if not date_str or not category or not description or not amount_str:
                malformed.append((line_no, row))
                continue

            # Validate date format
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                malformed.append((line_no, row))
                continue

            # Validate amount is a valid number
            try:
                amount = float(amount_str)
            except ValueError:
                malformed.append((line_no, row))
                continue

            valid.append(
                {
                    "date": date_obj,
                    "date_str": date_str,
                    "category": category,
                    "description": description,
                    "amount": amount,
                }
            )

    return valid, malformed


def group_by_month(transactions):
    """Group transactions by (year, month) and return ordered dict of month -> list."""
    monthly = defaultdict(list)
    for t in transactions:
        key = (t["date"].year, t["date"].month)
        monthly[key].append(t)
    return monthly


def group_by_category(transactions):
    """Group transactions by category and return dict of category -> total amount."""
    cat_totals = defaultdict(float)
    for t in transactions:
        cat_totals[t["category"]] += t["amount"]
    return dict(cat_totals)


def generate_report(input_path, output_path):
    """Generate the monthly expense report markdown."""
    valid, malformed = parse_transactions(input_path)

    if not valid:
        # Even with no valid transactions, produce a valid report
        pass

    monthly = group_by_month(valid)
    report_lines = []

    report_lines.append("# Monthly Expense Report")
    report_lines.append("")
    report_lines.append(f"**Input**: {input_path}")
    report_lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")

    # Summary section
    total_amount = sum(t["amount"] for t in valid)
    report_lines.append("## Summary")
    report_lines.append("")
    report_lines.append(f"- **Total transactions**: {len(valid)}")
    report_lines.append(f"- **Total amount**: ${total_amount:.2f}")
    report_lines.append("")

    # Malformed transactions section
    if malformed:
        report_lines.append("## Skipped (Malformed) Transactions")
        report_lines.append("")
        report_lines.append(
            f"The following {len(malformed)} transaction(s) could not be parsed and were skipped:"
        )
        report_lines.append("")
        report_lines.append("| Line | Date | Category | Description | Amount | Reason |")
        report_lines.append("|------|------|----------|-------------|--------|--------|")
        for line_no, row in malformed:
            amount_val = row.get("amount", "").strip()
            reason = (
                "missing or invalid amount"
                if not amount_val
                else "invalid amount format"
            )
            report_lines.append(
                f"| {line_no} | {row.get('date','')} | {row.get('category','')} | {row.get('description','')} | {amount_val} | {reason} |"
            )
        report_lines.append("")

    # Monthly breakdown
    report_lines.append("## Monthly Breakdown")
    report_lines.append("")

    for (year, month) in sorted(monthly.keys()):
        month_name = datetime(year, month, 1).strftime("%B %Y")
        month_txns = monthly[(year, month)]
        month_total = sum(t["amount"] for t in month_txns)

        report_lines.append(f"### {month_name}")
        report_lines.append("")
        report_lines.append(f"**Total**: ${month_total:.2f}")
        report_lines.append("")

        # Per-category summary for this month
        cat_totals = group_by_category(month_txns)
        report_lines.append("**By Category**:")
        report_lines.append("")
        for cat in sorted(cat_totals.keys()):
            report_lines.append(f"- {cat}: ${cat_totals[cat]:.2f}")
        report_lines.append("")

        # Individual transactions
        report_lines.append("**Transactions**:")
        report_lines.append("")
        report_lines.append("| Date | Description | Category | Amount |")
        report_lines.append("|------|-------------|----------|--------|")
        for t in month_txns:
            report_lines.append(
                f"| {t['date_str']} | {t['description']} | {t['category']} | ${t['amount']:.2f} |"
            )
        report_lines.append("")

    # Overall category summary
    all_cat_totals = group_by_category(valid)
    report_lines.append("## Category Summary")
    report_lines.append("")
    for cat in sorted(all_cat_totals.keys()):
        report_lines.append(f"- {cat}: ${all_cat_totals[cat]:.2f}")
    report_lines.append("")

    report_content = "\n".join(report_lines)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"Report written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate monthly expense report from CSV")
    parser.add_argument("--input", required=True, help="Path to input expense CSV")
    parser.add_argument("--output", required=True, help="Path to output report markdown")
    args = parser.parse_args()

    generate_report(args.input, args.output)


if __name__ == "__main__":
    main()
