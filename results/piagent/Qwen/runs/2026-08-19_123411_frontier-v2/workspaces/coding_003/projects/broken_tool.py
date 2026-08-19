"""CLI entry point for the monthly-total tool.

Usage:
    python broken_tool.py                 # default demo: [10, 20, "30"]
    python broken_tool.py --values 1 2 3  # custom values
    python broken_tool.py --csv data.csv  # read amounts from a CSV file
    python broken_tool.py --file out.txt  # write report to a file
"""

from __future__ import annotations

import argparse
import sys

from parser import parse_csv, parse_values
from validator import validate_values, ValidationError
from computer import compute_total
from reporter import print_report, write_report


def monthly_total(raw_input: list) -> float | None:
    """One-call convenience wrapper that chains parse → validate → compute.

    Returns:
        The computed total, or None when input cannot be parsed.
    """
    parsed = parse_values(raw_input)
    if parsed is None:
        return None
    try:
        validated = validate_values(parsed)
    except ValidationError:
        return None
    return compute_total(validated)


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    ap = argparse.ArgumentParser(
        description="Calculate monthly totals from raw values or CSV data."
    )
    ap.add_argument(
        "--values", nargs="+", default=None,
        help="Space-separated raw values (ints, floats, or number strings)"
    )
    ap.add_argument(
        "--csv", default=None,
        help="Path to a CSV file with an 'amount' column"
    )
    ap.add_argument(
        "--file", default=None,
        help="Optional output file for the report"
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    """Run the tool and return an exit code."""
    args = _build_parser().parse_args(argv)

    # Determine the data source
    if args.csv:
        parsed = parse_csv(args.csv)
        if parsed is None:
            print("Error: could not parse CSV file", file=sys.stderr)
            return 1
    elif args.values is not None:
        parsed = parse_values(args.values)
        if parsed is None:
            print("Error: no valid values provided", file=sys.stderr)
            return 1
    else:
        # Default demo – matches original behaviour
        parsed = parse_values([10, 20, "30"])

    try:
        validated = validate_values(parsed)
    except ValidationError as exc:
        print(f"Validation error: {exc}", file=sys.stderr)
        return 1

    total = compute_total(validated)

    if args.file:
        write_report(validated, total, args.file)
    else:
        print_report(validated, total)

    return 0


if __name__ == "__main__":
    sys.exit(main())
