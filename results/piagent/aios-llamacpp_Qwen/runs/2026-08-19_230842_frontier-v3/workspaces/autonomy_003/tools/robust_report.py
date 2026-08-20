"""Robust report tool: reads a CSV and writes a plain-text summary."""

import argparse
import csv
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Generate robust report from CSV data.")
    parser.add_argument("--input", required=True, help="Input CSV file path.")
    parser.add_argument("--output", required=True, help="Output text file path.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    # Validate input exists
    if not input_path.is_file():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Read CSV robustly
    try:
        with open(input_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # Sum the 'amount' column if present, skipping missing values
        total_amount = 0.0
        for row in rows:
            amt = row.get("amount", "").strip()
            if amt:
                try:
                    total_amount += float(amt)
                except ValueError:
                    pass  # skip unparseable values

        # Write output (empty dataset is valid)
        output_text = f"Records: {len(rows)}\nTotal: {total_amount:.2f}\n"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_text)

        print(f"Report written to {output_path}")
        sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
