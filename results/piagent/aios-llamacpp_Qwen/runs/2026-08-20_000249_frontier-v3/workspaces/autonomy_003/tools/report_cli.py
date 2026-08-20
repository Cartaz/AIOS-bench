import argparse
import csv
from pathlib import Path
from datetime import datetime


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()

    input_path = Path(a.input)
    if not input_path.is_file():
        print(f"Error: input file '{a.input}' not found", flush=True)
        raise SystemExit(1)

    with open(input_path, newline='') as f:
        rows = list(csv.DictReader(f))

    # Calculate revenue/amount total, handling missing/invalid values
    total = 0.0
    for row in rows:
        # Try to sum 'revenue' or 'amount' column
        amount_str = row.get('revenue', row.get('amount', ''))
        if amount_str:
            try:
                total += float(amount_str)
            except (ValueError, TypeError):
                pass

    # Generate HTML report
    html_lines = []
    html_lines.append('<!DOCTYPE html>')
    html_lines.append('<html><head><title>Report</title></head><body>')
    html_lines.append(f'<h1>Report - {input_path.name}</h1>')
    html_lines.append(f'<p>Total rows: {len(rows)}</p>')
    html_lines.append(f'<p>Total: {total:.2f}</p>')
    html_lines.append('<table border="1"><tr>')

    if rows:
        headers = list(rows[0].keys())
        html_lines.append(''.join(f'<th>{h}</th>' for h in headers))
        html_lines.append('</tr>')
        for row in rows:
            html_lines.append('<tr>')
            for h in headers:
                val = row.get(h, '')
                if val is None:
                    val = ''
                html_lines.append(f'<td>{val}</td>')
            html_lines.append('</tr>')

    html_lines.append('</table>')
    html_lines.append('</body></html>')

    output_path = Path(a.output)
    output_path.write_text('\n'.join(html_lines), encoding='utf-8')


if __name__ == '__main__':
    main()
