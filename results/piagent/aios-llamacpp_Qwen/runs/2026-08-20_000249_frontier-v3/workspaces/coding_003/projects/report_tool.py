"""Refactored report tool – delegates to parser/validator/reporter modules."""

import argparse
import csv
import json
import sys
from pathlib import Path

# Support both: direct execution (standalone) and package import
try:
    from .parser import read_csv
    from .reporter import generate_html_report, generate_text_report
except ImportError:
    # Standalone mode – fall back to inline
    def read_csv(path):
        with open(path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def generate_html_report(rows, output_path=None):
        from .validator import validate_rows, aggregate
        from .reporter import generate_html_report as _ghr
        return _ghr(rows, output_path)

    def generate_text_report(rows):
        from .validator import validate_rows
        from .reporter import generate_text_report as _gtr
        return _gtr(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="CSV reporting tool")
    parser.add_argument("--input", required=True, help="Path to input CSV file")
    parser.add_argument("--output", required=True, help="Path to output file")
    args = parser.parse_args()

    try:
        rows = read_csv(args.input)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output = Path(args.output)

    # Route to appropriate output format
    suffix = output.suffix.lower()
    if suffix == ".html":
        generate_html_report(rows, str(output))
    elif suffix in (".txt", ".text"):
        content = generate_text_report(rows)
        output.write_text(content, encoding="utf-8")
    else:
        # Default: JSON (preserves original CLI contract)
        json.dump({"rows": len(rows)}, output.open("w"))

    return 0


if __name__ == "__main__":
    sys.exit(main())

