#!/usr/bin/env python3
"""Produce a monthly expense report from data/expenses.csv."""

import csv
import os
from collections import defaultdict
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(SCRIPT_DIR)
EXPENSES_CSV = os.path.join(WORKSPACE, "data", "expenses.csv")
REPORTS_DIR = os.path.join(WORKSPACE, "reports")

# --- Read source data ---
rows = []
with open(EXPENSES_CSV, newline="") as f:
    reader = csv.DictReader(f)
    # Validate header
    assert reader.fieldnames == ["date", "category", "description", "amount"], (
        f"Unexpected header: {reader.fieldnames}"
    )
    for r in reader:
        r["amount"] = float(r["amount"])
        r["date_parsed"] = datetime.strptime(r["date"], "%Y-%m-%d")
        rows.append(r)

# --- Group by month ---
monthly = defaultdict(list)
for r in rows:
    month_key = r["date_parsed"].strftime("%Y-%m")
    monthly[month_key].append(r)

# --- Build report ---
os.makedirs(REPORTS_DIR, exist_ok=True)
report_lines = []
report_lines.append("# Monthly Expense Report")
report_lines.append("")

grand_total = 0.0
grand_count = 0

for month_key in sorted(monthly.keys()):
    items = monthly[month_key]
    month_total = sum(i["amount"] for i in items)
    grand_total += month_total
    grand_count += len(items)

    month_name = items[0]["date_parsed"].strftime("%B %Y")
    report_lines.append(f"## {month_name}")
    report_lines.append("")
    report_lines.append("| Date | Category | Description | Amount |")
    report_lines.append("|------|----------|-------------|--------|")
    for item in items:
        report_lines.append(
            f"| {item['date']} | {item['category']} | {item['description']} | {item['amount']:.2f} |"
        )
    report_lines.append("")
    report_lines.append(f"**Subtotal: ${month_total:.2f}** ({len(items)} items)")
    report_lines.append("")

    # Category breakdown
    cat_totals = defaultdict(float)
    for item in items:
        cat_totals[item["category"]] += item["amount"]
    report_lines.append("### Breakdown by Category")
    report_lines.append("")
    for cat in sorted(cat_totals):
        pct = (cat_totals[cat] / month_total) * 100 if month_total else 0
        report_lines.append(f"- **{cat}**: ${cat_totals[cat]:.2f} ({pct:.1f}%)")
    report_lines.append("")

# Grand summary
report_lines.append("## Summary")
report_lines.append("")
report_lines.append(f"- **Total Expenses**: ${grand_total:.2f}")
report_lines.append(f"- **Total Transactions**: {grand_count}")
report_lines.append("")

# Category breakdown across all months
all_cats = defaultdict(float)
for r in rows:
    all_cats[r["category"]] += r["amount"]
report_lines.append("### Total by Category")
report_lines.append("")
for cat in sorted(all_cats):
    pct = (all_cats[cat] / grand_total) * 100 if grand_total else 0
    report_lines.append(f"- **{cat}**: ${all_cats[cat]:.2f} ({pct:.1f}%)")
report_lines.append("")
report_lines.append("---")
report_lines.append("*Report generated automatically.*")

report_path = os.path.join(REPORTS_DIR, "monthly-expense-report.md")
with open(report_path, "w") as f:
    f.write("\n".join(report_lines) + "\n")

print(f"Report saved to {report_path}")
print(f"Total: ${grand_total:.2f} across {grand_count} transactions")
