#!/usr/bin/env python3
"""Step 3: Consume summary JSON and chart JSON to produce the final report.

Reads the outputs of step1_summary.py and step2_chart.py to produce
a human-readable final report in markdown format.

Usage:
    python tools/step3_report.py \
        --summary reports/summary.json \
        --chart reports/chart.json \
        --output reports/final_report.md

Exits with code 1 if any upstream artifact is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def build_report(summary_path: str, chart_path: str, output_path: str) -> None:
    """Read summary and chart JSON, produce final markdown report."""
    summary_file = Path(summary_path)
    if not summary_file.is_file():
        print(f"Error: summary file not found: {summary_path}", file=sys.stderr)
        sys.exit(1)

    chart_file = Path(chart_path)
    if not chart_file.is_file():
        print(f"Error: chart file not found: {chart_path}", file=sys.stderr)
        sys.exit(1)

    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    chart = json.loads(chart_file.read_text(encoding="utf-8"))

    lines: list[str] = []
    lines.append("# Final Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # --- Summary section ---
    lines.append("## 1. Data Summary")
    lines.append("")
    lines.append(f"- **Rows:** {summary.get('row_count', 0)}")
    lines.append(f"- **Columns:** {', '.join(summary.get('column_names', []))}")
    lines.append("")

    lines.append("### Column Statistics")
    lines.append("")
    lines.append("| Column | Count | Sum | Mean | Min | Max |")
    lines.append("|--------|-------|-----|------|-----|-----|")

    columns = summary.get("columns", {})
    for col_name, stats in columns.items():
        count = stats.get("count", 0)
        if count == 0:
            lines.append(f"| {col_name} | 0 | — | — | — | — |")
        else:
            s = stats["sum"]
            m = stats["mean"]
            mn = stats["min"]
            mx = stats["max"]
            lines.append(f"| {col_name} | {count} | {s} | {m} | {mn} | {mx} |")

    lines.append("")

    # --- Chart section ---
    lines.append("## 2. Chart")
    lines.append("")
    lines.append(f"- **Type:** {chart.get('chart_type', 'N/A')}")
    lines.append(f"- **Title:** {chart.get('title', 'N/A')}")
    lines.append("")

    datasets = chart.get("datasets", [])
    if datasets:
        lines.append("### Dataset Details")
        lines.append("")
        for ds in datasets:
            label = ds.get("label", "Unknown")
            description = ds.get("description", "")
            lines.append(f"#### {label}")
            lines.append(f"- {description}")
            lines.append("")
    else:
        lines.append("*No datasets available for charting.*")
        lines.append("")

    # --- Recommendations ---
    lines.append("## 3. Insights")
    lines.append("")
    metadata = chart.get("metadata", {})
    row_count = metadata.get("row_count", 0)
    if row_count == 0:
        lines.append("- The dataset is empty; no actionable insights can be generated.")
    else:
        lines.append(f"- Analysis covered {row_count} rows of data.")
        for col_name, stats in columns.items():
            if stats.get("count", 0) > 0:
                lines.append(f"- {col_name}: mean={stats['mean']}, range=[{stats['min']}, {stats['max']}]")

    lines.append("")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Final report written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 3: Generate final report from summary and chart JSON"
    )
    parser.add_argument("--summary", required=True, help="Path to summary JSON")
    parser.add_argument("--chart", required=True, help="Path to chart JSON")
    parser.add_argument("--output", required=True, help="Path to output report (markdown)")
    args = parser.parse_args()
    build_report(args.summary, args.chart, args.output)


if __name__ == "__main__":
    main()
