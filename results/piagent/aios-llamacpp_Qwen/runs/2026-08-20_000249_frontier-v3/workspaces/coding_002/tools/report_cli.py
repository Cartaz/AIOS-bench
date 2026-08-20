import argparse
import csv
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()

    input_path = Path(a.input)
    if not input_path.is_file():
        print(f"Error: input file not found: {a.input}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, newline='') as f:
        rows = list(csv.DictReader(f))

    # Sum the 'revenue' column if present, otherwise sum 'amount'
    total = 0.0
    for row in rows:
        val = row.get('revenue') or row.get('amount')
        if val is not None and val.strip():
            try:
                total += float(val)
            except ValueError:
                pass  # skip malformed values

    output = f"""\
<html>
<head><title>Report</title></head>
<body>
<h1>Report</h1>
<p>Total: {total:.2f}</p>
</body>
</html>
"""
    Path(a.output).write_text(output, encoding='utf-8')


if __name__ == '__main__':
    main()
