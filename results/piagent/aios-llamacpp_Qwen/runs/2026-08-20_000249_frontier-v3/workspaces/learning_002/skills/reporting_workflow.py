#!/usr/bin/env python3
"""
Recurring monthly reporting workflow.

Reads a sales/transaction CSV, validates it, calculates totals, and writes a
summary report.  Generalized — no fixture-specific totals are hard-coded.

Usage:
    python skills/reporting_workflow.py --input data/sales.csv --output reports/monthly-sales.md
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_csv(path: Path) -> list[dict[str, str]]:
    """Return rows as a list of dicts. Raises SystemExit on I/O errors."""
    if not path.exists():
        print(f"Error: input file not found: {path}", file=sys.stderr)
        sys.exit(1)
    if path.stat().st_size == 0:
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def is_numeric(value: str) -> bool:
    """Return True when *value* can be parsed as a number."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def validate_header(rows: list[dict[str, str]]) -> list[str]:
    """Return the list of header column names (empty list when file is empty)."""
    if not rows:
        return []
    return list(rows[0].keys())


def compute_totals(rows: list[dict[str, str]], header: list[str]) -> dict:
    """
    Iterate *rows*, skipping entries whose numeric columns are invalid.

    Returns a dict with keys: total_revenue, total_units, valid_rows, skipped_rows,
    products.
    """
    # Try to identify which columns map to "units" and "revenue".
    # We look for columns whose name contains 'unit', 'qty', 'sold' (for units)
    # and 'revenue', 'gross', 'amount', 'usd' (for revenue).
    unit_cols = [c for c in header if any(k in c.lower() for k in ("unit", "qty"))]
    revenue_cols = [c for c in header if any(k in c.lower() for k in ("revenue", "gross", "amount", "usd"))]
    product_cols = [c for c in header if any(k in c.lower() for k in ("product", "sku", "item"))]

    units_col = unit_cols[0] if unit_cols else None
    revenue_col = revenue_cols[0] if revenue_cols else None
    product_col = product_cols[0] if product_cols else None

    total_revenue = 0.0
    total_units = 0
    valid_rows = 0
    skipped_rows = 0
    products: set[str] = set()

    for row in rows:
        # Validate units
        units_valid = True
        if units_col is not None:
            val = row.get(units_col, "")
            if not is_numeric(val):
                units_valid = False

        # Validate revenue
        revenue_valid = True
        if revenue_col is not None:
            val = row.get(revenue_col, "")
            if not is_numeric(val):
                revenue_valid = False

        if not units_valid or not revenue_valid:
            skipped_rows += 1
            continue

        units = int(float(row.get(units_col, "0")))
        revenue = float(row.get(revenue_col, "0"))
        total_units += units
        total_revenue += revenue
        valid_rows += 1

        if product_col is not None:
            products.add(row.get(product_col, "").strip())

    return {
        "total_revenue": total_revenue,
        "total_units": total_units,
        "valid_rows": valid_rows,
        "skipped_rows": skipped_rows,
        "products": sorted(products),
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def write_md_report(summary: dict, path: Path) -> None:
    """Write a Markdown summary report."""
    lines = [
        "# Monthly Sales Summary",
        "",
        f"- **Total Revenue:** {summary['total_revenue']:.2f}",
        f"- **Total Units:** {summary['total_units']}",
        f"- **Valid Rows:** {summary['valid_rows']}",
        f"- **Skipped Rows:** {summary['skipped_rows']}",
        "",
        "## Products",
        "",
    ]
    if summary["products"]:
        for p in summary["products"]:
            lines.append(f"- {p}")
    else:
        lines.append("_No products detected._")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_html_report(summary: dict, path: Path) -> None:
    """Write an HTML summary report."""
    products_html = ""
    if summary["products"]:
        products_html = "<ul>" + "".join(f"<li>{p}</li>" for p in summary["products"]) + "</ul>"
    else:
        products_html = "<p>No products detected.</p>"

    html = f"""\
<!DOCTYPE html>
<html>
<head><title>Monthly Sales Summary</title></head>
<body>
<h1>Monthly Sales Summary</h1>
<p><strong>Total Revenue:</strong> {summary['total_revenue']:.2f}</p>
<p><strong>Total Units:</strong> {summary['total_units']}</p>
<p><strong>Valid Rows:</strong> {summary['valid_rows']}</p>
<p><strong>Skipped Rows:</strong> {summary['skipped_rows']}</p>
<h2>Products</h2>
{products_html}
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def write_report(summary: dict, path: Path) -> None:
    """Dispatch to the correct writer based on file extension."""
    if path.suffix.lower() == ".html":
        write_html_report(summary, path)
    else:
        write_md_report(summary, path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recurring monthly reporting workflow — validate, compute totals, write report."
    )
    parser.add_argument("--input", required=True, help="Path to the source CSV file.")
    parser.add_argument("--output", required=True, help="Path for the generated report.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    # 1. Read
    rows = read_csv(input_path)

    # 2. Validate header
    header = validate_header(rows)
    if not header:
        print("Warning: CSV appears to be empty or has no header.", file=sys.stderr)

    # 3. Compute totals
    summary = compute_totals(rows, header)

    # 4. Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(summary, output_path)

    print(f"Report written to {output_path} ({summary['valid_rows']} valid rows).")


if __name__ == "__main__":
    main()
