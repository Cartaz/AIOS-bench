#!/usr/bin/env python3
"""CLI tool that reads a CSV file and produces a deterministic HTML report.

Usage:
    python tools/report_cli.py --input <csv_file> --output <html_file>

The tool validates CSV headers, handles malformed rows gracefully, and produces
a self-contained HTML report with a table of the data plus summary statistics.

Exit codes:
    0  - Success
    1  - Invalid arguments, missing file, or unrecoverable CSV issues
"""

import argparse
import csv
import sys
from pathlib import Path


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="report_cli",
        description="Read a CSV file and write a deterministic HTML report.",
        epilog="Example: python tools/report_cli.py --input data/sales.csv --output report.html",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input CSV file.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to the output HTML file.",
    )
    return parser.parse_args(argv)


def read_csv(filepath):
    """Read and validate a CSV file.

    Returns a list of dicts (one per row) after validation.
    Malformed rows (wrong column count, non-numeric in numeric columns)
    are skipped with a warning printed to stderr, but the tool still
    succeeds if at least one valid row exists.
    """
    path = Path(filepath)
    if not path.exists():
        print(f"Error: input file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    if path.stat().st_size == 0:
        print(f"Error: input file is empty: {filepath}", file=sys.stderr)
        sys.exit(1)

    try:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                print("Error: CSV file has no header row.", file=sys.stderr)
                sys.exit(1)

            headers = list(reader.fieldnames)

            # Validate: header must not contain blanks
            for i, h in enumerate(headers):
                if h is None or h.strip() == "":
                    print(f"Error: header column {i} is empty.", file=sys.stderr)
                    sys.exit(1)

            rows = []
            num_cols = len(headers)
            # Try to find a numeric column for summary stats
            numeric_indices = []
            for col_idx, col_name in enumerate(headers):
                numeric_indices.append(col_idx)  # tentative

            line_num = 1  # header is line 1
            for row in reader:
                line_num += 1
                # Check row has exactly the right number of fields
                raw_keys = list(row.keys())
                # DictReader may add a key for extra fields beyond headers
                # We only consider keys that match known headers
                if len(raw_keys) != num_cols:
                    # Could be extra fields – filter
                    filtered = {k: row[k] for k in headers if k in row}
                    if len(filtered) != num_cols:
                        print(
                            f"Warning: line {line_num}: expected {num_cols} fields, "
                            f"got {len(raw_keys)} – skipping.",
                            file=sys.stderr,
                        )
                        continue
                    row = filtered

                validated = {}
                for h in headers:
                    val = row.get(h, "")
                    if val is None:
                        val = ""
                    validated[h] = val.strip()

                # Detect numeric columns from the first valid row
                rows.append((validated, line_num))

            if not rows:
                print("Error: no valid data rows found in the CSV.", file=sys.stderr)
                sys.exit(1)

            # Now classify numeric columns by checking all values
            numeric_indices = []
            for col_idx, col_name in enumerate(headers):
                is_numeric = True
                for row_vals, _ in rows:
                    raw_val = row_vals.get(col_name, "")
                    if raw_val == "":
                        continue  # empty is ok
                    try:
                        float(raw_val)
                    except (ValueError, TypeError):
                        is_numeric = False
                        break
                if is_numeric:
                    numeric_indices.append(col_idx)

            return headers, rows, numeric_indices

    except csv.Error as exc:
        print(f"Error: CSV parsing failed: {exc}", file=sys.stderr)
        sys.exit(1)


def build_summary(headers, rows, numeric_indices):
    """Build a summary dict from the rows."""
    summary = {}
    for col_idx in numeric_indices:
        col_name = headers[col_idx]
        values = []
        for row_vals, _ in rows:
            raw = row_vals.get(col_name, "")
            if raw == "":
                continue
            try:
                values.append(float(raw))
            except (ValueError, TypeError):
                pass
        if values:
            summary[col_name] = {
                "sum": sum(values),
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": sum(values) / len(values),
            }
    return summary


def render_html(headers, rows, summary, numeric_indices):
    """Render a self-contained HTML report string."""
    # Build table rows
    table_rows = ""
    for row_vals, _ in rows:
        td_cells = ""
        for h in headers:
            td_cells += f"<td>{_escape_html(row_vals.get(h, ''))}</td>\n"
        table_rows += f"<tr>{td_cells}</tr>\n"

    # Build summary section
    summary_html = ""
    if summary:
        summary_rows = ""
        for col_name, stats in summary.items():
            formatted_sum = _format_number(stats["sum"])
            formatted_min = _format_number(stats["min"])
            formatted_max = _format_number(stats["max"])
            formatted_mean = _format_number(stats["mean"])
            summary_rows += (
                f"<tr><td>{_escape_html(col_name)}</td>"
                f"<td>{stats['count']}</td>"
                f"<td>{formatted_min}</td>"
                f"<td>{formatted_max}</td>"
                f"<td>{formatted_sum}</td>"
                f"<td>{formatted_mean}</td></tr>\n"
            )
        summary_html = f"""
    <section>
      <h2>Summary Statistics</h2>
      <table>
        <thead><tr><th>Column</th><th>Count</th><th>Min</th><th>Max</th><th>Sum</th><th>Mean</th></tr></thead>
        <tbody>{summary_rows}</tbody>
      </table>
    </section>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CSV Report</title>
<style>
  body {{ font-family: sans-serif; margin: 2em; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5em; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
  th {{ background: #f4f4f4; }}
  h1, h2 {{ color: #333; }}
</style>
</head>
<body>
  <h1>CSV Report</h1>
  <p>Rows: {len(rows)}</p>
  <table>
    <thead><tr>{''.join(f'<th>{_escape_html(h)}</th>' for h in headers)}</tr></thead>
    <tbody>{table_rows}</tbody>
  </table>{summary_html}
</body>
</html>"""
    return html


def _escape_html(text):
    """Minimal HTML escaping."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _format_number(value):
    """Format a number for display: use 2 decimal places if float, else int."""
    if value == int(value):
        return str(int(value))
    # Round to 2 decimal places for cleanliness, but preserve needed precision
    rounded = round(value, 2)
    if rounded == int(rounded):
        return f"{rounded:.2f}"
    return f"{rounded:.2f}"


def main(argv=None):
    args = parse_args(argv)

    headers, rows, numeric_indices = read_csv(args.input)
    summary = build_summary(headers, rows, numeric_indices)
    html = render_html(headers, rows, summary, numeric_indices)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"Report written to {out_path} ({len(rows)} rows)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
