"""Robust report tool that handles empty and missing input datasets."""
import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Robust report generator")
    parser.add_argument("--input", required=True, help="Input CSV file")
    parser.add_argument("--output", required=True, help="Output file")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: input file '{args.input}' does not exist", file=sys.stderr)
        return 1

    try:
        with open(input_path, "r") as f:
            content = f.read().strip()
        if not content:
            with open(output_path, "w") as f:
                f.write("report: empty dataset\n")
            return 0
        lines = content.splitlines()
        count = len(lines) - 1  # subtract header
        with open(output_path, "w") as f:
            f.write(f"report: {count} rows processed\n")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
