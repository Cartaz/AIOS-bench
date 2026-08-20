#!/usr/bin/env python3
"""Robust report tool that handles empty and missing datasets gracefully."""

import argparse
import csv
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Generate robust report from CSV")
    p.add_argument("--input", required=True, help="Input CSV file")
    p.add_argument("--output", required=True, help="Output text file")
    a = p.parse_args()

    input_path = Path(a.input)
    if not input_path.is_file():
        print(f"Error: input file '{a.input}' not found", file=sys.stderr)
        sys.exit(1)

    with open(input_path, newline="") as f:
        rows = list(csv.DictReader(f))

    lines = []
    lines.append(f"Dataset: {a.input}")
    lines.append(f"Rows: {len(rows)}")

    if not rows:
        lines.append("No data rows found.")
        with open(a.output, "w") as out:
            out.write("\n".join(lines) + "\n")
        sys.exit(0)

    # Summarize numeric columns
    for key in rows[0]:
        vals = []
        for row in rows:
            v = row.get(key, "").strip()
            if v:
                try:
                    vals.append(float(v))
                except ValueError:
                    pass
        if vals:
            total = sum(vals)
            lines.append(f"{key}: count={len(vals)}, sum={total}, min={min(vals)}, max={max(vals)}")

    with open(a.output, "w") as out:
        out.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
