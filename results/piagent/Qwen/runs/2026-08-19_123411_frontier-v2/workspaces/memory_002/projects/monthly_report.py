#!/usr/bin/env python3
"""
Monthly Sales Report Generator

Respects stored workflow preferences retrieved from the workspace:
  - PREFERENCE 1: Output format must be Markdown (.md), per procedures/current.md
    (the previous procedure used .txt — that was explicitly retired).
  - PREFERENCE 2: A review/validation step must precede sharing the report,
    per procedures/current.md step 5.

This tool reads data/sales.csv, computes totals, generates a Markdown report
at reports/monthly-sales.md, and validates it before "sharing" (printing a
ready-to-publish confirmation).
"""

import csv
import os
import sys
from pathlib import Path

# Resolve paths relative to the workspace root
WORKSPACE = Path(__file__).resolve().parent  # projects/
ROOT = WORKSPACE.parent  # workspace root
SALES_CSV = ROOT / "data" / "sales.csv"
REPORTS_DIR = ROOT / "reports"
REPORT_FILE = REPORTS_DIR / "monthly-sales.md"


def load_sales(path: Path) -> list[dict]:
    """Load and validate the sales CSV."""
    if not path.exists():
        raise FileNotFoundError(f"Sales CSV not found at {path}")
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        # Validate header
        expected = {"date", "product", "units", "revenue"}
        if reader.fieldnames is None or set(reader.fieldnames) != expected:
            raise ValueError(
                f"Invalid header in {path}: "
                f"expected {expected}, got {reader.fieldnames}"
            )
        rows = list(reader)
    # Validate numeric fields
    for i, row in enumerate(rows):
        try:
            row["units"] = int(row["units"])
            row["revenue"] = float(row["revenue"])
        except (ValueError, KeyError) as e:
            raise ValueError(
                f"Row {i + 2} in {path} has non-numeric fields: {e}"
            )
    return rows


def compute_summary(rows: list[dict]) -> dict:
    """Compute total revenue, total units, and per-product breakdown."""
    total_revenue = 0.0
    total_units = 0
    by_product: dict[str, dict] = {}

    for row in rows:
        total_revenue += row["revenue"]
        total_units += row["units"]
        prod = row["product"]
        if prod not in by_product:
            by_product[prod] = {"units": 0, "revenue": 0.0}
        by_product[prod]["units"] += row["units"]
        by_product[prod]["revenue"] += row["revenue"]

    return {
        "total_revenue": total_revenue,
        "total_units": total_units,
        "by_product": dict(sorted(by_product.items())),
    }


def generate_markdown(summary: dict) -> str:
    """Generate a Markdown report string.

    PREFERENCE 1 applied here: output is Markdown (.md), not plain .txt.
    """
    lines = [
        "# Monthly Sales Report",
        "",
        f"**Total Revenue:** ${summary['total_revenue']:,.2f}",
        f"**Total Units Sold:** {summary['total_units']:,}",
        "",
        "| Product | Units | Revenue  |",
        "|---------|------:|---------:|",
    ]
    for name, stats in summary["by_product"].items():
        lines.append(
            f"| {name} | {stats['units']:,} | ${stats['revenue']:,.2f} |"
        )
    lines.append("")  # trailing newline
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Review step — PREFERENCE 2
# ---------------------------------------------------------------------------

def review_report(content: str) -> bool:
    """
    PREFERENCE 2 applied here: validate the report before sharing.

    Checks performed:
      1. Content is non-empty.
      2. Contains the expected Markdown header.
      3. Contains at least one data row (table body).
    """
    if not content.strip():
        print("[REVIEW] FAIL: Report is empty.")
        return False
    if "# Monthly Sales Report" not in content:
        print("[REVIEW] FAIL: Report missing title heading.")
        return False
    if "|" not in content:
        print("[REVIEW] FAIL: Report missing product table.")
        return False

    print("[REVIEW] PASS: Report validated successfully.")
    return True


def save_report(content: str, path: Path) -> None:
    """Write the report to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[SAVE] Report saved to {path}")


def share_report(path: Path) -> None:
    """Signal that the report is ready for sharing."""
    print(f"[SHARE] Report is ready: {path.resolve()}")
    print("[SHARE] Contents:")
    print("-" * 60)
    print(path.read_text(encoding="utf-8"))
    print("-" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Monthly Sales Report Generator ===")
    print(f"Workspace: {ROOT.resolve()}")
    print()

    # Step 1: Load & validate
    print("[1/5] Loading sales CSV …")
    rows = load_sales(SALES_CSV)
    print(f"  Loaded {len(rows)} rows from {SALES_CSV}")

    # Step 2: Compute summary
    print("[2/5] Computing summary …")
    summary = compute_summary(rows)
    print(f"  Total revenue: ${summary['total_revenue']:,.2f}")
    print(f"  Total units:   {summary['total_units']:,}")

    # Step 3: Generate Markdown report
    print("[3/5] Generating Markdown report …")
    content = generate_markdown(summary)

    # Step 4: Review (PREFERENCE 2)
    print("[4/5] Reviewing report …")
    if not review_report(content):
        print("[ABORT] Review failed — stopping.")
        sys.exit(1)

    # Step 5: Save & share
    print("[5/5] Saving and sharing …")
    save_report(content, REPORT_FILE)
    share_report(REPORT_FILE)

    print()
    print("=== Done ===")


if __name__ == "__main__":
    main()
