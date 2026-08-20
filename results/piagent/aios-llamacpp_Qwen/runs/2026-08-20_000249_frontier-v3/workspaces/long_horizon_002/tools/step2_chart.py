#!/usr/bin/env python3
"""Step 2: Consume a summary JSON and produce chart-ready data.

Reads the summary JSON produced by step1_summary.py and generates
chart data suitable for rendering (bar charts, pie charts, line charts).

Output is a JSON object with:
  - chart_type: suggested chart type based on data
  - datasets: list of chart dataset entries
  - labels: x-axis labels
  - title: a generated title for the chart
  - metadata: copy of relevant summary metadata

Usage:
    python tools/step2_chart.py --input reports/summary.json --output reports/chart.json

Exits with code 1 if the summary input is missing or invalid.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_chart(summary_path: str, output_path: str) -> None:
    """Read summary JSON, produce chart data JSON."""
    path = Path(summary_path)
    if not path.is_file():
        print(f"Error: summary file not found: {summary_path}", file=sys.stderr)
        sys.exit(1)

    summary = json.loads(path.read_text(encoding="utf-8"))

    columns = summary.get("columns", {})
    numeric_cols = {
        k: v for k, v in columns.items() if v.get("count", 0) > 0
    }

    # Determine chart type
    if len(numeric_cols) == 1:
        chart_type = "bar"
        title = f"{next(iter(numeric_cols))} summary"
    elif len(numeric_cols) == 0:
        chart_type = "none"
        title = "No numeric data to chart"
    else:
        chart_type = "grouped-bar"
        title = "Multi-column summary"

    # Build datasets
    datasets = []
    for col_name, stats in numeric_cols.items():
        datasets.append({
            "label": col_name,
            "data": [stats["mean"], stats["min"], stats["max"], stats["sum"]],
            "description": f"Mean={stats['mean']}, Min={stats['min']}, Max={stats['max']}, Sum={stats['sum']}",
        })

    # Build labels
    labels = ["mean", "min", "max", "sum"] if datasets else []

    chart = {
        "chart_type": chart_type,
        "title": title,
        "datasets": datasets,
        "labels": labels,
        "metadata": {
            "row_count": summary.get("row_count", 0),
            "column_names": summary.get("column_names", []),
        },
    }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(chart, indent=2) + "\n", encoding="utf-8")
    print(f"Chart data written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 2: Generate chart data from summary JSON")
    parser.add_argument("--input", required=True, help="Path to summary JSON")
    parser.add_argument("--output", required=True, help="Path to chart JSON output")
    args = parser.parse_args()
    build_chart(args.input, args.output)


if __name__ == "__main__":
    main()
