#!/usr/bin/env python3
"""Robust report tool — handles empty files and missing inputs gracefully.

Usage:
    python tools/robust_report.py --input <csv> --output <txt>
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Robust CSV-to-text report.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    p = Path(args.input)

    if not p.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(p, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            # Completely empty file
            result = "No data found."
        else:
            rows = list(reader)
            if not rows:
                result = "No data found."
            else:
                parts = [f"Rows: {len(rows)}", ""]
                for row in rows:
                    parts.append(", ".join(f"{k}: {v}" for k, v in row.items()))
                result = "\n".join(parts)

    output_dir = Path(args.output).parent
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(result + "\n", encoding="utf-8")
    print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
