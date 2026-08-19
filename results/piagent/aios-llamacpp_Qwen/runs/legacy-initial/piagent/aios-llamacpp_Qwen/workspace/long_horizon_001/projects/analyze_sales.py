#!/usr/bin/env python3
"""
Generate July 2026 monthly sales summary.
Follows the current procedure:
1. Export the monthly sales CSV.
2. Validate the header and numeric fields.
3. Calculate total revenue and units.
4. Save the summary as reports/monthly-sales.md.
5. Review the result before sharing it.
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SALES_CSV = WORKSPACE / "data" / "sales.csv"
REPORT_FILE = WORKSPACE / "reports" / "monthly-sales.md"


def load_sales(path: Path) -> list[dict]:
    """Load sales CSV and return list of row dicts."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def validate(rows: list[dict], header: list[str]) -> None:
    """Validate header matches expected columns and numeric fields parse."""
    expected = ["date", "product", "units", "revenue"]
    if header != expected:
        raise ValueError(f"Unexpected header: {header}, expected {expected}")
    for i, row in enumerate(rows):
        try:
            int(row["units"])
            float(row["revenue"])
        except (ValueError, KeyError) as e:
            raise ValueError(f"Row {i + 1} has invalid numeric field: {e}")


def calculate_totals(rows: list[dict]) -> dict:
    """Calculate total revenue, units, and per-product breakdown."""
    total_revenue = 0.0
    total_units = 0
    product_breakdown = {}

    for row in rows:
        units = int(row["units"])
        revenue = float(row["revenue"])
        total_revenue += revenue
        total_units += units
        product = row["product"]
        if product not in product_breakdown:
            product_breakdown[product] = {"units": 0, "revenue": 0.0}
        product_breakdown[product]["units"] += units
        product_breakdown[product]["revenue"] += revenue

    return {
        "total_revenue": total_revenue,
        "total_units": total_units,
        "product_breakdown": product_breakdown,
        "num_transactions": len(rows),
    }


def generate_report(totals: dict, period: str = "July 2026") -> str:
    """Generate a Markdown report."""
    lines = [
        f"# Monthly Sales Report — {period}",
        "",
        f"**Report generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Revenue | ${totals['total_revenue']:.2f} |",
        f"| Total Units Sold | {totals['total_units']} |",
        f"| Number of Transactions | {totals['num_transactions']} |",
        "",
        "## Breakdown by Product",
        "",
        "| Product | Units | Revenue |",
        "|---------|-------|---------|",
    ]
    for product, stats in sorted(totals["product_breakdown"].items()):
        lines.append(
            f"| {product} | {stats['units']} | ${stats['revenue']:.2f} |"
        )

    lines.append("")
    lines.append("## Transactions")
    lines.append("")
    lines.append("| Date | Product | Units | Revenue |")
    lines.append("|")

    return "\n".join(lines)


def main():
    # Step 1: Load the sales CSV
    print(f"Loading sales data from {SALES_CSV} ...")
    rows = load_sales(SALES_CSV)

    # Step 2: Validate
    header = list(rows[0].keys()) if rows else []
    validate(rows, header)
    print(f"  Validation passed ({len(rows)} rows).")

    # Step 3: Calculate totals
    totals = calculate_totals(rows)

    # Step 4: Save report
    report = generate_report(totals)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Report saved to {REPORT_FILE}")

    # Step 5: Print report for review
    print()
    print(report)


if __name__ == "__main__":
    main()
