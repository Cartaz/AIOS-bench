#!/usr/bin/env python3
"""Robust report CLI – handles empty datasets gracefully.

Accepts --input (CSV) and --output (text) and produces a text report.
Exit codes:
  0 – success (even for empty datasets)
  1 – failure (missing file, invalid args, etc.)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_workspace_root = Path(__file__).resolve().parent.parent
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from projects.parser import read_csv
from projects.validator import validate_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate text report from CSV data")
    parser.add_argument("--input", required=True, help="Input CSV file path")
    parser.add_argument("--output", required=True, help="Output text file path")
    args = parser.parse_args()

    try:
        rows = read_csv(args.input)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    cleaned = validate_rows(rows)

    lines: list[str] = []
    lines.append(f"Total rows: {len(cleaned)}")
    for row in cleaned:
        lines.append(" | ".join(f"{k}={v}" for k, v in row.items()))

    content = "\n".join(lines) + "\n"
    Path(args.output).write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
