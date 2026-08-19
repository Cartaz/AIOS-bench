"""
Report generation module.

Produces deterministic, human-readable Markdown reports from validated
records.  Supports both expense and sales schemas.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Dict, List, Union

from .records import (
    ExpenseRecord,
    SalesRecord,
)

# Unified record type alias
Record = Union[ExpenseRecord, SalesRecord]


def generate_expense_report(records: List[ExpenseRecord]) -> str:
    """Generate a Markdown expense report.

    Output is **deterministic**: categories and dates are sorted.
    """
    lines: List[str] = []
    lines.append("# Monthly Expense Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(UTC):%Y-%m-%d %H:%M:%S} UTC")
    lines.append("")

    # --- Summary ---
    total_amount = sum((r.amount for r in records), Decimal("0"))
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total records:** {len(records)}")
    lines.append(f"- **Total amount:** ${total_amount:.2f}")
    lines.append("")

    # --- By category (sorted deterministically) ---
    by_cat: Dict[str, List[ExpenseRecord]] = defaultdict(list)
    for r in records:
        by_cat[r.category.value].append(r)

    lines.append("## Expenses by Category")
    lines.append("")
    for cat in sorted(by_cat.keys()):
        items = by_cat[cat]
        cat_total = sum((r.amount for r in items), Decimal("0"))
        lines.append(f"### {cat.title()}")
        lines.append("")
        lines.append(f"Subtotal: ${cat_total:.2f}")
        lines.append("")
        lines.append("| Date | Description | Amount |")
        lines.append("|------|-------------|--------|")
        for r in sorted(items, key=lambda x: x.date):
            lines.append(f"| {r.date.isoformat()} | {r.description} | ${r.amount:.2f} |")
        lines.append("")

    # --- Individual entries ---
    lines.append("## All Entries")
    lines.append("")
    lines.append("| Date | Category | Description | Amount |")
    lines.append("|------|----------|-------------|--------|")
    for r in sorted(records, key=lambda x: x.date):
        lines.append(f"| {r.date.isoformat()} | {r.category.value} | {r.description} | ${r.amount:.2f} |")
    lines.append("")

    return "\n".join(lines)


def generate_sales_report(records: List[SalesRecord]) -> str:
    """Generate a Markdown sales report.

    Output is **deterministic**: products are sorted alphabetically.
    """
    lines: List[str] = []
    lines.append("# Monthly Sales Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(UTC):%Y-%m-%d %H:%M:%S} UTC")
    lines.append("")

    # --- Summary ---
    total_revenue = sum((r.revenue for r in records), Decimal("0"))
    total_units = sum((r.units for r in records), 0)
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total records:** {len(records)}")
    lines.append(f"- **Total units:** {total_units}")
    lines.append(f"- **Total revenue:** ${total_revenue:.2f}")
    lines.append("")

    # --- By product (sorted deterministically) ---
    by_prod: Dict[str, List[SalesRecord]] = defaultdict(list)
    for r in records:
        by_prod[r.product].append(r)

    lines.append("## Sales by Product")
    lines.append("")
    for prod in sorted(by_prod.keys()):
        items = by_prod[prod]
        prod_revenue = sum((r.revenue for r in items), Decimal("0"))
        prod_units = sum((r.units for r in items), 0)
        avg_price = prod_revenue / prod_units if prod_units else Decimal("0")
        lines.append(f"### {prod}")
        lines.append("")
        lines.append(f"- Units sold: {prod_units}")
        lines.append(f"- Revenue: ${prod_revenue:.2f}")
        lines.append(f"- Average price per unit: ${avg_price:.2f}")
        lines.append("")
        lines.append("| Date | Units | Revenue |")
        lines.append("|------|-------|---------|")
        for r in sorted(items, key=lambda x: x.date):
            lines.append(f"| {r.date.isoformat()} | {r.units} | ${r.revenue:.2f} |")
        lines.append("")

    # --- Individual entries ---
    lines.append("## All Entries")
    lines.append("")
    lines.append("| Date | Product | Units | Revenue |")
    lines.append("|------|---------|-------|---------|")
    for r in sorted(records, key=lambda x: x.date):
        lines.append(f"| {r.date.isoformat()} | {r.product} | {r.units} | ${r.revenue:.2f} |")
    lines.append("")

    return "\n".join(lines)


def generate_report(schema: str, records: List[Record]) -> str:
    """Dispatch to the correct report generator."""
    if schema == "expense":
        return generate_expense_report(records)  # type: ignore[arg-type]
    elif schema == "sales":
        return generate_sales_report(records)  # type: ignore[arg-type]
    else:
        raise ValueError(f"Unknown schema: {schema!r}")


def save_report(content: str, filepath: str | None = None) -> str:
    """Write report to file and return the path."""
    import os
    if filepath is None:
        # Default: current working directory, deterministic name
        if not os.path.exists("reports"):
            os.makedirs("reports")
        filepath = "reports/report.md"
    else:
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(content)
    return filepath
