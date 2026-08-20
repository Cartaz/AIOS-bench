"""CLI report tool that generates HTML reports from CSV data."""
import argparse
import sys
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Report CLI tool")
    parser.add_argument("--input", required=True, help="Input CSV file")
    parser.add_argument("--output", required=True, help="Output HTML file")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: input file '{args.input}' does not exist", file=sys.stderr)
        return 1

    try:
        with open(input_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total_revenue = 0.0
        for row in rows:
            try:
                total_revenue += float(row.get("revenue", row.get("amount", "0")))
            except (ValueError, TypeError):
                pass  # skip non-numeric entries

        html = f"""<!DOCTYPE html>
<html><head><title>Report</title></head>
<body>
<h1>Report Summary</h1>
<p>Total revenue: {total_revenue:.2f}</p>
<p>Rows: {len(rows)}</p>
</body></html>
"""
        with open(output_path, "w") as f:
            f.write(html)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
