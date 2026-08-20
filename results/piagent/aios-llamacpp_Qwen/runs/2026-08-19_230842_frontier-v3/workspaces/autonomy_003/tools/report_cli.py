"""CLI report tool: reads a CSV, writes an HTML summary report."""

import argparse
import csv
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Generate HTML report from CSV data.")
    parser.add_argument("--input", required=True, help="Input CSV file path.")
    parser.add_argument("--output", required=True, help="Output HTML file path.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    # Validate input exists
    if not input_path.is_file():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Read and process CSV
    try:
        with open(input_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # Sum revenue if the 'revenue' column exists
        total_revenue = 0.0
        for row in rows:
            rev = row.get("revenue", "").strip()
            if rev:
                try:
                    total_revenue += float(rev)
                except ValueError:
                    pass  # skip unparseable values

        revenue_str = f"{total_revenue:.2f}"

    except Exception as e:
        print(f"Error processing CSV: {e}", file=sys.stderr)
        sys.exit(1)

    # Write HTML output
    html = f"""\
<!DOCTYPE html>
<html>
<head><title>Report</title></head>
<body>
<h1>Sales Report</h1>
<p>Total Revenue: {revenue_str}</p>
<p>Records: {len(rows)}</p>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report written to {output_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()
