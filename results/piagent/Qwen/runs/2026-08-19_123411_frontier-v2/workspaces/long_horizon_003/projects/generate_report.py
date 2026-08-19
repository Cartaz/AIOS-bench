#!/usr/bin/env python3
"""Generate monthly sales summary report from CSV data.

Follows the current operating procedure:
1. Export the monthly sales CSV.
2. Validate the header and numeric fields.
3. Calculate total revenue and units.
4. Save the summary as reports/monthly-sales.md.
5. Review the result before sharing it.
"""

import csv
import os
import sys
from collections import defaultdict

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_sales(filepath):
    """Read and validate sales CSV, returning list of dicts with numeric fields."""
    records = []
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        # Validate header
        expected = {"date", "product", "units", "revenue"}
        if not expected.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"Sales CSV header mismatch. Expected {expected}, got {reader.fieldnames}")
        for row in reader:
            row["units"] = int(row["units"])
            row["revenue"] = float(row["revenue"])
            records.append(row)
    return records


def read_expenses(filepath):
    """Read and validate expenses CSV."""
    records = []
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        expected = {"date", "category", "description", "amount"}
        if not expected.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"Expenses CSV header mismatch. Expected {expected}, got {reader.fieldnames}")
        for row in reader:
            row["amount"] = float(row["amount"])
            records.append(row)
    return records


def summarize_sales(records):
    """Calculate per-product and total summaries."""
    product_units = defaultdict(int)
    product_revenue = defaultdict(float)
    total_units = 0
    total_revenue = 0.0

    for r in records:
        product_units[r["product"]] += r["units"]
        product_revenue[r["product"]] += r["revenue"]
        total_units += r["units"]
        total_revenue += r["revenue"]

    return {
        "total_units": total_units,
        "total_revenue": total_revenue,
        "products": dict(sorted(product_units.items())),
        "product_revenue": dict(sorted(product_revenue.items())),
    }


def summarize_expenses(records):
    """Calculate per-category and total expense summaries."""
    category_amount = defaultdict(float)
    total = 0.0
    for r in records:
        category_amount[r["category"]] += r["amount"]
        total += r["amount"]
    return {
        "total": total,
        "categories": dict(sorted(category_amount.items())),
    }


def generate_report(sales_file, expenses_file, output_file):
    """Generate the full monthly report."""
    sales = read_sales(sales_file)
    expenses = read_expenses(expenses_file)
    sales_summary = summarize_sales(sales)
    expense_summary = summarize_expenses(expenses)

    lines = []
    lines.append("# Monthly Sales Summary — July 2026")
    lines.append("")
    lines.append("## Sales Overview")
    lines.append("")
    lines.append(f"- **Total Units Sold:** {sales_summary['total_units']}")
    lines.append(f"- **Total Revenue:** ${sales_summary['total_revenue']:.2f}")
    lines.append("")
    lines.append("## Revenue by Product")
    lines.append("")
    lines.append("| Product | Units Sold | Revenue |")
    lines.append("|---------|-----------|---------|")
    for product in sorted(sales_summary["products"]):
        units = sales_summary["products"][product]
        revenue = sales_summary["product_revenue"][product]
        lines.append(f"| {product} | {units} | ${revenue:.2f} |")
    lines.append(f"| **TOTAL** | **{sales_summary['total_units']}** | **${sales_summary['total_revenue']:.2f}** |")
    lines.append("")
    lines.append("## Monthly Expenses")
    lines.append("")
    lines.append("| Category | Amount |")
    lines.append("|----------|--------|")
    for category, amount in sorted(expense_summary["categories"].items()):
        lines.append(f"| {category} | ${amount:.2f} |")
    lines.append(f"| **TOTAL** | **${expense_summary['total']:.2f}** |")
    lines.append("")
    lines.append("## Net Result")
    lines.append("")
    net = sales_summary["total_revenue"] - expense_summary["total"]
    lines.append(f"- Revenue: ${sales_summary['total_revenue']:.2f}")
    lines.append(f"- Expenses: ${expense_summary['total']:.2f}")
    lines.append(f"- **Net: ${net:.2f}**")
    lines.append("")
    lines.append("---")
    lines.append("*Report generated following current operating procedure.*")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Report saved to {output_file}")
    return output_file


if __name__ == "__main__":
    sales_path = os.path.join(WORKSPACE, "data", "sales.csv")
    expenses_path = os.path.join(WORKSPACE, "data", "expenses.csv")
    report_path = os.path.join(WORKSPACE, "reports", "monthly-sales.md")
    generate_report(sales_path, expenses_path, report_path)
