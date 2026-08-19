#!/usr/bin/env python3
"""csv_report.py — Read a CSV file and write a concise HTML report.

Reads a CSV file, computes summary statistics for every numeric column,
and produces a standalone HTML file that can be viewed in any browser.

Usage:
    python csv_report.py input.csv
    python csv_report.py input.csv -o report.html
    python csv_report.py input.csv --title "My Report"

Options:
    --help, -h      Show this help message and exit.
    -o, --output    Write output to the given file (default: <input>.html).
    --title TEXT    Set the report title (default: derived from filename).
"""

from __future__ import annotations

import argparse
import csv
import html
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="csv_report",
        description="Read a CSV file and generate a concise HTML report with summary statistics.",
        epilog="Example: python csv_report.py data/sales.csv -o report.html",
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to the input CSV file.",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Path for the output HTML file. "
             "Defaults to <input>.html in the same directory.",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Title displayed in the HTML report. "
             "Defaults to the CSV filename without extension.",
    )
    args = parser.parse_args(argv)

    # --- Input validation ---
    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"Input file not found: {args.input}")
    if not input_path.is_file():
        parser.error(f"Input path is not a file: {args.input}")
    if input_path.suffix.lower() != ".csv":
        parser.error(f"Input file must have a .csv extension: {args.input}")

    # Default output path
    if args.output is None:
        out = input_path.with_suffix(".html")
        args.output = str(out)

    if input_path.resolve() == Path(args.output).resolve():
        parser.error("Input and output files must be different.")

    return args


def _is_numeric(value: str) -> bool:
    """Return True if *value* can be parsed as a float."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def read_csv(path: str) -> Tuple[List[str], List[List[str]]]:
    """Read a CSV file and return (headers, rows).

    Validates that the file is non-empty and has at least one header row
    and one data row.  Returns raw string data — no type coercion yet.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        rows_list = list(reader)

    if not rows_list:
        raise ValueError(f"CSV file is empty: {path}")

    headers = rows_list[0]
    if not headers or all(h.strip() == "" for h in headers):
        raise ValueError(f"CSV file has no header row: {path}")

    data_rows = rows_list[1:]
    if not data_rows:
        raise ValueError(f"CSV file has only a header and no data rows: {path}")

    # All rows must have the same number of columns as the header
    for idx, row in enumerate(data_rows, start=2):
        if len(row) != len(headers):
            raise ValueError(
                f"Row {idx} has {len(row)} column(s), expected {len(headers)}"
            )

    return headers, data_rows


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def compute_stats(values: List[float]) -> Dict[str, float]:
    """Compute basic descriptive statistics for a list of floats."""
    n = len(values)
    if n == 0:
        return {}

    mean = sum(values) / n
    sorted_vals = sorted(values)
    median = sorted_vals[n // 2] if n % 2 else (
        (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    )

    variance = sum((x - mean) ** 2 for x in values) / n  # population
    std_dev = math.sqrt(variance)

    return {
        "count": n,
        "min": min(values),
        "max": max(values),
        "mean": mean,
        "median": median,
        "std_dev": std_dev,
    }


def identify_numeric_columns(
    headers: List[str], rows: List[List[str]]
) -> Dict[str, List[float]]:
    """Return {column_name: [float_values]} for every numeric column."""
    numeric: Dict[str, List[float]] = {}
    for col_idx, header in enumerate(headers):
        col_values = [row[col_idx].strip() for row in rows]
        num_vals = [float(v) for v in col_values if _is_numeric(v)]
        # A column is considered numeric if at least 50% of its values are numeric
        if len(col_values) > 0 and len(num_vals) / len(col_values) >= 0.5:
            numeric[header] = num_vals
    return numeric


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _stat_row(label: str, value: float) -> str:
    """Format a single statistics row."""
    display = f"{value:,.2f}" if value != int(value) else f"{value:,.0f}"
    return (
        f"      <tr>"
        f"<td>{html.escape(label)}</td>"
        f"<td>{html.escape(display)}</td>"
        f"</tr>\n"
    )


def build_html_report(
    title: str,
    headers: List[str],
    rows: List[List[str]],
    numeric_cols: Dict[str, List[float]],
) -> str:
    """Build the full HTML report string."""
    num_cols_html = ""
    for col_name, values in numeric_cols.items():
        stats = compute_stats(values)
        col_stats = (
            f"    <th>{html.escape(col_name)}</th>\n"
            + "".join(
                f"    <tr><td>{html.escape(s)}</td><td>{html.escape(v)}</td></tr>\n"
                for s, v in [
                    ("Count", str(stats["count"])),
                    ("Min", f"{stats['min']:,.2f}"),
                    ("Max", f"{stats['max']:,.2f}"),
                    ("Mean", f"{stats['mean']:,.2f}"),
                    ("Median", f"{stats['median']:,.2f}"),
                    ("Std Dev", f"{stats['std_dev']:,.2f}"),
                ]
            )
        )
        num_cols_html += f"  <div class=\"num-col\">\n{col_stats}\n  </div>\n"

    # --- Data table ---
    table_rows = ""
    for row_idx, row in enumerate(rows, start=1):
        cells = "".join(
            f"<td>{html.escape(cell)}</td>" for cell in row
        )
        table_rows += f"    <tr>{cells}</tr>\n"

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 960px;
    margin: 2rem auto;
    padding: 0 1rem;
    color: #222;
    background: #fafafa;
  }}
  h1 {{ color: #1a1a2e; border-bottom: 2px solid #16213e; padding-bottom: 0.5rem; }}
  .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 2rem;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }}
  th, td {{
    border: 1px solid #ddd;
    padding: 0.5rem 0.75rem;
    text-align: left;
    font-size: 0.9rem;
  }}
  th {{ background: #16213e; color: #fff; }}
  tr:nth-child(even) {{ background: #f4f4f9; }}
  .stats-section {{ margin-bottom: 2rem; }}
  .stats-section h2 {{ color: #16213e; font-size: 1.1rem; }}
  .num-col {{
    background: #fff;
    border-radius: 6px;
    padding: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    margin-bottom: 1rem;
  }}
  .num-col table {{ box-shadow: none; margin: 0; }}
  .num-col td:first-child {{ font-weight: 600; color: #555; width: 120px; }}
</style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="meta">Generated on {__import__("datetime").date.today().isoformat()} &middot;
     {len(rows)} row(s) &middot; {len(headers)} column(s)</p>

  <div class="stats-section">
    <h2>Summary Statistics (numeric columns)</h2>
    {num_cols_html.rstrip()}
  </div>

  <h2>Data</h2>
  <table>
    <tr>{"".join(f"<th>{html.escape(h)}</th>" for h in headers)}</tr>
{table_rows}  </table>

</body>
</html>
"""
    return html_body


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv)

    try:
        headers, rows = read_csv(args.input)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    numeric_cols = identify_numeric_columns(headers, rows)

    if args.title:
        title = args.title
    else:
        title = Path(args.input).stem.replace("-", " ").replace("_", " ").title()

    report = build_html_report(title, headers, rows, numeric_cols)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
