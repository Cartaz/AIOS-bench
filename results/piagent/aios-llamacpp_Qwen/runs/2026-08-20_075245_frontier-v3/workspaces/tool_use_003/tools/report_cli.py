#!/usr/bin/env python3
"""Report CLI that reads a CSV and produces an HTML report."""

import argparse
import csv
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Generate HTML report from CSV")
    p.add_argument("--input", required=True, help="Input CSV file")
    p.add_argument("--output", required=True, help="Output HTML file")
    a = p.parse_args()

    input_path = Path(a.input)
    if not input_path.is_file():
        print(f"Error: input file '{a.input}' not found", file=sys.stderr)
        sys.exit(1)

    with open(input_path, newline="") as f:
        rows = list(csv.DictReader(f))

    # Build HTML
    lines = []
    lines.append("<!DOCTYPE html>")
    lines.append("<html><head><title>Report</title></head><body>")
    lines.append(f"<h1>Report ({len(rows)} rows)</h1>")
    
    # Compute totals for numeric columns
    numeric_totals = {}
    if rows:
        for key in rows[0]:
            total = 0.0
            for row in rows:
                v = row.get(key, "").strip()
                if v:
                    try:
                        total += float(v)
                    except ValueError:
                        pass
            if total:
                # Format to 2 decimal places if it's a money-like value
                numeric_totals[key] = total
    
    lines.append("<table border='1'>")

    if rows:
        # Header row
        lines.append("<tr>")
        for key in rows[0]:
            lines.append(f"<th>{key}</th>")
        lines.append("</tr>")

        # Data rows - handle malformed/missing values gracefully
        for row in rows:
            lines.append("<tr>")
            for key in rows[0]:
                val = row.get(key, "")
                if val is None:
                    val = ""
                # Strip whitespace, show empty for missing
                val = val.strip() if val else ""
                lines.append(f"<td>{val}</td>")
            lines.append("</tr>")

    # Add totals row if numeric columns found
    if numeric_totals:
        lines.append("<tr>")
        lines.append(f"<td><b>Total</b></td>")
        for key in rows[0]:
            if key in numeric_totals:
                val = numeric_totals[key]
                # Format with 2 decimal places
                lines.append(f"<td>{val:.2f}</td>")
            else:
                lines.append("<td></td>")
        lines.append("</tr>")

    lines.append("</table>")
    lines.append("</body></html>")

    with open(a.output, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
