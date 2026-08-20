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
    total_revenue = 0.0
    with open(input_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            # Try to sum up revenue or amount fields if they exist and are valid
            for key in ('revenue', 'amount'):
                if key in row and row[key]:
                    try:
                        total_revenue += float(row[key])
                    except (ValueError, TypeError):
                        pass

    total_rows = len(rows)

    html = f"""<!DOCTYPE html>
<html>
<head><title>Report</title></head>
<body>
<h1>Data Report</h1>
<p>Total rows: {total_rows}</p>
<p>Sum of revenue/amount: {total_revenue:.2f}</p>
<table border="1">
<tr>
{"<th>" + "</th><th>".join(rows[0].keys()) + "</th>" if rows else "<th>No data</th>"}
</tr>
"""
    for row in rows:
        html += "<tr>"
        html += "".join(f"<td>{v}</td>" for v in row.values())
        html += "</tr>\n"
    html += """</table>
</body>
</html>"""

    output_path.write_text(html, encoding='utf-8')
    print(f"Report written to {output_path}")


if __name__ == '__main__':
    main()
