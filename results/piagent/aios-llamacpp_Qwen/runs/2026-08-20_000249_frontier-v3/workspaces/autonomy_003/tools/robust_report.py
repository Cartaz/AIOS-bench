import argparse
import csv
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()

    input_path = Path(a.input)
    if not input_path.is_file():
        print(f"Error: input file '{a.input}' not found", flush=True)
        raise SystemExit(1)

    total = 0.0
    row_count = 0

    with open(input_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_count += 1
            amount_str = row.get('amount', row.get('revenue', ''))
            if amount_str:
                try:
                    total += float(amount_str)
                except (ValueError, TypeError):
                    pass

    output_path = Path(a.output)
    output_path.write_text(
        f"rows={row_count}\ntotal={total:.2f}\n",
        encoding='utf-8'
    )


if __name__ == '__main__':
    main()
