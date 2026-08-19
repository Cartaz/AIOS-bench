#!/usr/bin/env python3
"""CLI tool that reads a sales CSV and writes a deterministic HTML report."""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path


EXPECTED_HEADERS = {"date", "product", "units", "revenue"}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Read a sales CSV file and generate a deterministic HTML report."
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to the input CSV file (must have date,product,units,revenue headers).",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Path to the output HTML file.",
    )
    return parser.parse_args(argv)


def read_and_validate(input_path):
    """Read CSV, validate headers and rows. Returns (headers, rows) or raises SystemExit."""
    path = Path(input_path)
    if not path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)

            # Read and validate header
            try:
                header_line = next(reader)
            except StopIteration:
                print("Error: CSV file is empty.", file=sys.stderr)
                sys.exit(1)

            headers = [h.strip().lower() for h in header_line]
            header_set = set(headers)
            missing = EXPECTED_HEADERS - header_set
            if missing:
                print(
                    f"Error: CSV is missing required header(s): {', '.join(sorted(missing))}",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Build column index map
            col_index = {h: idx for idx, h in enumerate(headers)}

            rows = []
            for line_no, row in enumerate(reader, start=2):
                # Skip completely blank lines
                if not row or all(cell.strip() == "" for cell in row):
                    continue

                # Check column count
                expected_len = len(EXPECTED_HEADERS)
                if len(row) != expected_len:
                    print(
                        f"Error: line {line_no} has {len(row)} columns, expected {expected_len}. "
                        f"Row: {csv.QUOTE_MINIMAL.join(row)}",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                date_str = row[col_index["date"]].strip()
                product = row[col_index["product"]].strip()
                units_str = row[col_index["units"]].strip()
                revenue_str = row[col_index["revenue"]].strip()

                # Validate units
                try:
                    units = int(units_str)
                except ValueError:
                    print(
                        f"Error: line {line_no}: 'units' value '{units_str}' is not an integer.",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                # Validate revenue
                try:
                    revenue = float(revenue_str)
                except ValueError:
                    print(
                        f"Error: line {line_no}: 'revenue' value '{revenue_str}' is not a number.",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                # Validate date format (ISO: YYYY-MM-DD)
                try:
                    parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    print(
                        f"Error: line {line_no}: 'date' value '{date_str}' is not a valid date (expected YYYY-MM-DD).",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                rows.append(
                    {
                        "date": parsed_date,
                        "product": product,
                        "units": units,
                        "revenue": revenue,
                    }
                )

    except PermissionError:
        print(f"Error: permission denied reading {input_path}", file=sys.stderr)
        sys.exit(1)
    except csv.Error as e:
        print(f"Error: could not parse CSV: {e}", file=sys.stderr)
        sys.exit(1)

    return headers, rows


def generate_html(headers, rows):
    """Generate deterministic HTML from validated rows."""
    # Sort rows deterministically by date, then product
    sorted_rows = sorted(rows, key=lambda r: (r["date"], r["product"]))

    # Build table rows
    table_rows = ""
    total_units = 0
    total_revenue = 0.0
    for r in sorted_rows:
        total_units += r["units"]
        total_revenue += r["revenue"]
        table_rows += (
            f"      <tr>\n"
            f"        <td>{r['date'].strftime('%Y-%m-%d')}</td>\n"
            f"        <td>{r['product']}</td>\n"
            f"        <td>{r['units']}</td>\n"
            f"        <td>{r['revenue']:.2f}</td>\n"
            f"      </tr>\n"
        )

    # Compute per-product summary
    product_summary = {}
    for r in sorted_rows:
        p = r["product"]
        if p not in product_summary:
            product_summary[p] = {"units": 0, "revenue": 0.0, "count": 0}
        product_summary[p]["units"] += r["units"]
        product_summary[p]["revenue"] += r["revenue"]
        product_summary[p]["count"] += 1

    summary_rows = ""
    for p in sorted(product_summary.keys()):
        s = product_summary[p]
        summary_rows += (
            f"      <tr>\n"
            f"        <td>{p}</td>\n"
            f"        <td>{s['units']}</td>\n"
            f"        <td>{s['revenue']:.2f}</td>\n"
            f"        <td>{s['count']}</td>\n"
            f"      </tr>\n"
        )

    total_units_row = f"      <tr>\n        <td><strong>Total</strong></td>\n"
    total_units_row += f"        <td><strong>{total_units}</strong></td>\n"
    total_units_row += f"        <td><strong>{total_revenue:.2f}</strong></td>\n"
    total_units_row += f"        <td></td>\n      </tr>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sales Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2em; }}
    h1 {{ color: #333; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5em; }}
    th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
    th {{ background-color: #f0f0f0; }}
    tfoot td {{ font-weight: bold; background-color: #fafafa; }}
    .summary {{ margin-top: 1em; }}
  </style>
</head>
<body>
  <h1>Sales Report</h1>
  <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

  <h2>Transactions</h2>
  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th>Product</th>
        <th>Units</th>
        <th>Revenue</th>
      </tr>
    </thead>
    <tbody>
{table_rows}    </tbody>
    <tfoot>
{total_units_row}    </tfoot>
  </table>

  <h2 class="summary">Product Summary</h2>
  <table>
    <thead>
      <tr>
        <th>Product</th>
        <th>Total Units</th>
        <th>Total Revenue</th>
        <th>Transactions</th>
      </tr>
    </thead>
    <tbody>
{summary_rows}    </tbody>
  </table>
</body>
</html>
"""
    return html


def main(argv=None):
    args = parse_args(argv)

    headers, rows = read_and_validate(args.input)

    html = generate_html(headers, rows)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: wrote {len(rows)} rows to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
