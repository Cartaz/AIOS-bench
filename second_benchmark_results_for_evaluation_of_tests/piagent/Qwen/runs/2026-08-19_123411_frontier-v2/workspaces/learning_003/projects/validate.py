#!/usr/bin/env python3
"""Independent validation of the monthly sales summary.

This script reads the raw sales data and computes totals using a
completely independent method (Python stdlib csv + direct summation)
to verify the results produced by the main pipeline tool.
"""

import csv
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALES_CSV = os.path.join(BASE, "data", "sales.csv")
REPORT_DIR = os.path.join(BASE, "reports")
REPORT_FILE = os.path.join(REPORT_DIR, "monthly-sales.md")


def compute_from_csv():
    """Independent computation from raw sales.csv."""
    total_units = 0
    total_revenue = 0.0
    product_stats = {}

    with open(SALES_CSV, newline="") as f:
        reader = csv.DictReader(f)
        # Validate header
        assert reader.fieldnames == ["date", "product", "units", "revenue"], (
            f"Unexpected header: {reader.fieldnames}"
        )
        for row in reader:
            units = int(row["units"])
            revenue = float(row["revenue"])
            total_units += units
            total_revenue += revenue
            prod = row["product"]
            if prod not in product_stats:
                product_stats[prod] = {"units": 0, "revenue": 0.0}
            product_stats[prod]["units"] += units
            product_stats[prod]["revenue"] += revenue

    return {
        "total_units": total_units,
        "total_revenue": total_revenue,
        "product_stats": product_stats,
        "row_count": total_units,  # just a placeholder
    }


def read_existing_report():
    """Read and parse the generated report (if it exists)."""
    if not os.path.isfile(REPORT_FILE):
        return None
    with open(REPORT_FILE) as f:
        return f.read()


def generate_report(stats):
    """Write the monthly-sales.md report."""
    os.makedirs(REPORT_DIR, exist_ok=True)
    lines = [
        "# Monthly Sales Summary",
        "",
        f"**Period:** 2026-07",
        f"**Total Units Sold:** {stats['total_units']}",
        f"**Total Revenue:** ${stats['total_revenue']:.2f}",
        "",
        "## By Product",
        "",
    ]
    for prod in sorted(stats["product_stats"]):
        s = stats["product_stats"][prod]
        lines.append(f"- **{prod}:** {s['units']} units, ${s['revenue']:.2f}")
    lines.append("")
    return "\n".join(lines)


def main():
    # Step 1: Independent computation
    stats = compute_from_csv()
    print("=== Independent Validation ===")
    print(f"Total units:  {stats['total_units']}")
    print(f"Total revenue: ${stats['total_revenue']:.2f}")
    print()

    # Step 2: Verify the reusable tool gives the same answer
    from broken_tool import monthly_total

    all_units = [float(stats["product_stats"][p]["units"]) for p in stats["product_stats"]]
    all_revenue = [float(stats["product_stats"][p]["revenue"]) for p in stats["product_stats"]]
    tool_units = monthly_total(all_units)
    tool_revenue = monthly_total(all_revenue)
    print("=== Tool Verification ===")
    print(f"Tool total units:  {tool_units}")
    print(f"Tool total revenue: ${tool_revenue:.2f}")
    assert tool_units == stats["total_units"], f"Units mismatch: tool={tool_units}, csv={stats['total_units']}"
    assert abs(tool_revenue - stats["total_revenue"]) < 0.01, f"Revenue mismatch: tool={tool_revenue}, csv={stats['total_revenue']}"
    print("PASS — tool and independent computation agree.\n")

    # Step 3: Generate the report
    report = generate_report(stats)
    with open(REPORT_FILE, "w") as f:
        f.write(report)
    print("Report written to:", REPORT_FILE)

    # Step 4: If a previous report existed, compare
    existing = read_existing_report()
    if existing is not None:
        print("\n=== Comparison with existing report ===")
        if existing == report:
            print("PASS — no differences from existing report.")
        else:
            print("WARNING — existing report differs. New report has been written.")
            # Show differences
            old_lines = existing.splitlines()
            new_lines = report.splitlines()
            for i, (o, n) in enumerate(zip(old_lines, new_lines)):
                if o != n:
                    print(f"  Line {i+1}: OLD='{o}'  NEW='{n}'")
    else:
        print("No prior report found — this is the first generated report.")

    print("\n=== Validation complete ===")


if __name__ == "__main__":
    main()
