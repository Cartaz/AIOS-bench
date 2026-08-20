import argparse
import csv
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: input file '{args.input}' not found", file=sys.stderr)
        sys.exit(1)

    rows = []
    with open(input_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    total_rows = len(rows)

    lines = [f"Robust Report", f"Input: {args.input}", f"Total rows: {total_rows}"]
    if rows:
        lines.append(f"Columns: {', '.join(rows[0].keys())}")
    else:
        lines.append("No data rows found.")

    output_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"Report written to {output_path}")


if __name__ == '__main__':
    main()
