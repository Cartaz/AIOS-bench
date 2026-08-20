#!/usr/bin/env python3
"""CLI report generator: runs the 3-step pipeline end-to-end and produces HTML.

Usage:
    python tools/report_cli.py --input data/sales.csv --output report.html
    python tools/report_cli.py --input data/sales_alt.csv --output .hidden_alt.html

The output HTML contains the summary data including numeric values
from the input CSV. If the input file does not exist, exits with non-zero code.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path


def run_pipeline(input_path: str, output_path: str) -> None:
    """Execute the full 3-step pipeline and produce an HTML report."""
    input_file = Path(input_path)
    if not input_file.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # --- Step 1: Summary ---
    summary = build_summary(input_file)

    # --- Step 2: Chart data ---
    chart = build_chart_data(summary)

    # --- Step 3: HTML Report ---
    html = generate_html(summary, chart)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Report written to {output_path}")


def build_summary(input_file: Path) -> dict:
    """Produce summary dict from CSV."""
    with input_file.open(newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    columns = {}
    for col in fieldnames:
        values = [row.get(col, "") for row in rows]
        nums = [float(v) for v in values if v.strip() and _is_numeric(v)]
        if nums:
            columns[col] = {
                "count": len(nums),
                "sum": round(sum(nums), 4),
                "mean": round(sum(nums) / len(nums), 4),
                "min": min(nums),
                "max": max(nums),
            }
        else:
            columns[col] = {"count": 0, "sum": None, "mean": None, "min": None, "max": None}

    return {
        "row_count": len(rows),
        "column_names": list(fieldnames),
        "columns": columns,
        "_raw_rows": rows,
    }


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def build_chart_data(summary: dict) -> dict:
    """Produce chart data from summary."""
    numeric_cols = {k: v for k, v in summary["columns"].items() if v.get("count", 0) > 0}

    if len(numeric_cols) == 1:
        chart_type = "bar"
    else:
        chart_type = "grouped-bar"

    datasets = []
    for col_name, stats in numeric_cols.items():
        datasets.append({
            "label": col_name,
            "data": [stats["mean"], stats["min"], stats["max"], stats["sum"]],
            "description": f"Mean={stats['mean']:.2f}, Min={stats['min']:.2f}, Max={stats['max']:.2f}, Sum={stats['sum']:.2f}",
        })

    return {
        "chart_type": chart_type,
        "title": f"Analysis of {summary['column_names'][0] if summary['column_names'] else 'data'}",
        "datasets": datasets,
        "metadata": {
            "row_count": summary["row_count"],
            "column_names": summary["column_names"],
        },
    }


def generate_html(summary: dict, chart: dict) -> str:
    """Generate the final HTML report."""
    columns = summary.get("columns", {})
    numeric_cols = {k: v for k, v in columns.items() if v.get("count", 0) > 0}

    # Collect all numeric values for display
    numeric_values = []
    for col_name, stats in numeric_cols.items():
        if stats.get("sum") is not None:
            numeric_values.append(f'{stats["sum"]:.2f}')
        if stats.get("mean") is not None:
            numeric_values.append(f'{stats["mean"]:.2f}')

    row_count = summary.get("row_count", 0)
    column_names = summary.get("column_names", [])
    datasets = chart.get("datasets", [])

    # Build summary table rows
    table_rows = ""
    for col_name, stats in columns.items():
        if stats.get("count", 0) > 0:
            table_rows += f"<tr><td>{col_name}</td><td>{stats['count']}</td><td>{stats['sum']:.2f}</td><td>{stats['mean']:.2f}</td><td>{stats['min']:.2f}</td><td>{stats['max']:.2f}</td></tr>\n"
        else:
            table_rows += f"<tr><td>{col_name}</td><td>0</td><td>—</td><td>—</td><td>—</td><td>—</td></tr>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Final Report</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 2em; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
  th {{ background-color: #f0f0f0; }}
</style>
</head>
<body>
<h1>Final Report</h1>
<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<h2>1. Data Summary</h2>
<p>Rows: {row_count} | Columns: {', '.join(column_names)}</p>

<h2>2. Column Statistics</h2>
<table>
<tr><th>Column</th><th>Count</th><th>Sum</th><th>Mean</th><th>Min</th><th>Max</th></tr>
{table_rows}</table>

<h2>3. Chart</h2>
<p>Type: {chart.get('chart_type', 'N/A')} | Title: {chart.get('title', 'N/A')}</p>

<h3>Datasets</h3>
<ul>
{''.join(f'<li><b>{ds["label"]}</b>: {ds["description"]}</li>' for ds in datasets)}
</ul>

<h2>4. Insights</h2>
<ul>
<li>Analysis covered {row_count} rows of data.</li>
{''.join(f'<li>{col}: mean={stats["mean"]:.2f}, range=[{stats["min"]:.2f}, {stats["max"]:.2f}]</li>' for col, stats in numeric_cols.items())}
</ul>

<h2>5. Raw Values</h2>
<p>Numeric values in report: {', '.join(numeric_values)}</p>
</body>
</html>
"""
    return html


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end report pipeline CLI")
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--output", required=True, help="Path to output HTML report")
    args = parser.parse_args()
    run_pipeline(args.input, args.output)


if __name__ == "__main__":
    main()
