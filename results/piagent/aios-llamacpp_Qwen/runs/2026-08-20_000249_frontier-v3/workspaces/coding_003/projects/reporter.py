"""Reporting module – generates output reports."""

from __future__ import annotations

from .validator import validate_rows, aggregate


def generate_html_report(rows: list[dict[str, str]], output_path: str | None = None) -> str:
    """Generate an HTML report string from CSV row dicts.

    - Identifies numeric columns automatically.
    - Produces a table of rows and a summary with totals.
    - Writes to *output_path* if provided.
    - Returns the HTML string.
    """
    cleaned = validate_rows(rows)

    # Detect numeric columns
    numeric_cols: list[str] = []
    if cleaned:
        sample = cleaned[0]
        numeric_cols = [k for k, v in sample.items() if isinstance(v, (int, float))]

    totals = aggregate(cleaned, numeric_cols)

    # Build HTML
    lines: list[str] = []
    lines.append("<!DOCTYPE html>")
    lines.append("<html><head><title>Report</title></head><body>")
    lines.append("<h1>Report</h1>")

    # Summary
    if totals:
        lines.append("<h2>Summary</h2><table border='1'>")
        lines.append("<tr><th>Metric</th><th>Total</th></tr>")
        for col, total in totals.items():
            lines.append(f"<tr><td>{col}</td><td>{total:.2f}</td></tr>")
        lines.append("</table>")

    # Detail table
    if cleaned:
        headers = list(cleaned[0].keys())
        lines.append("<h2>Details</h2><table border='1'>")
        lines.append("<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>")
        for row in cleaned:
            lines.append("<tr>" + "".join(f"<td>{_fmt(v)}</td>" for v in row.values()) + "</tr>")
        lines.append("</table>")
        lines.append(f"<p>Total rows: {len(cleaned)}</p>")

    lines.append("</body></html>")
    html = "\n".join(lines)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(html)

    return html


def generate_text_report(rows: list[dict[str, str]]) -> str:
    """Generate a simple text report."""
    cleaned = validate_rows(rows)
    lines: list[str] = []
    lines.append(f"Total rows: {len(cleaned)}")
    for row in cleaned:
        lines.append(" | ".join(f"{k}={_fmt(v)}" for k, v in row.items()))
    return "\n".join(lines)


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)
