#!/usr/bin/env python3
"""CLI entry-point for the refactored reporting tool.

Accepts --input (CSV) and --output (HTML) and produces an HTML report
with row details and numeric column totals.

Exit codes:
  0 – success
  1 – failure (missing file, invalid args, etc.)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the workspace root is on sys.path so that `projects` is importable
_workspace_root = Path(__file__).resolve().parent.parent
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from projects.parser import read_csv
from projects.reporter import generate_html_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HTML report from CSV data")
    parser.add_argument("--input", required=True, help="Input CSV file path")
    parser.add_argument("--output", required=True, help="Output HTML file path")
    args = parser.parse_args()

    try:
        rows = read_csv(args.input)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    generate_html_report(rows, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
