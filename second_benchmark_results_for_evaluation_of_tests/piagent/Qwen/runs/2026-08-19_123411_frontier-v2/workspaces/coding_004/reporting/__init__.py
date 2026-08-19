"""
CLI entry-point for the CSV reporting utility.

Usage:
    python -m reporting.main <csv_path> [output_path]
"""

import argparse
import sys
from pathlib import Path

from .loader import parse_csv_file
from .report import generate_report, save_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reporting.main",
        description="Generate Markdown reports from expense or sales CSV data.",
    )
    parser.add_argument(
        "csv_path",
        help="Path to the CSV file to process.",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output Markdown file path (default: reports/report.md).",
    )
    args = parser.parse_args(argv)

    csv_path = Path(args.csv_path)

    # --- Load and validate ---
    try:
        schema, records = parse_csv_file(csv_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"VALIDATION ERROR: {exc}", file=sys.stderr)
        return 2

    # --- Generate report ---
    try:
        content = generate_report(schema, records)
    except Exception as exc:
        print(f"REPORT GENERATION ERROR: {exc}", file=sys.stderr)
        return 3

    # --- Save ---
    output_path = save_report(content, args.output)
    print(f"Report saved to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
