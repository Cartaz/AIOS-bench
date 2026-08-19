#!/usr/bin/env python3
"""Tests for sales_to_html.py covering normal input and failure cases."""

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(__file__), "sales_to_html.py")


def _run(input_path, output_path):
    """Helper: run the CLI and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, SCRIPT, "--input", str(input_path), "--output", str(output_path)],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _write_csv(path, lines):
    """Helper to write a CSV file with given header + data lines."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def _read_output(path):
    """Read the output HTML file as text."""
    return Path(path).read_text(encoding="utf-8")


# ── Fixtures: normal valid CSV ──────────────────────────────────────────────

VALID_CSV_LINES = [
    "date,product,units,revenue",
    "2026-07-01,A,10,100",
    "2026-07-03,B,4,80",
    "2026-07-08,A,12,120",
    "2026-07-15,C,2,100",
    "2026-07-22,B,5,100",
    "2026-07-29,A,8,80",
]

# ── Tests ───────────────────────────────────────────────────────────────────

def test_normal_input_writes_valid_html():
    """Given a well-formed CSV, the tool produces an HTML file with expected structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "sales.csv")
        html_path = os.path.join(tmpdir, "out.html")
        _write_csv(csv_path, VALID_CSV_LINES)

        rc, stdout, stderr = _run(csv_path, html_path)

        assert rc == 0, f"Expected exit code 0, got {rc}. stderr: {stderr}"
        assert os.path.isfile(html_path), "Output HTML file was not created."

        html = _read_output(html_path)
        # Structure checks
        assert "<!DOCTYPE html>" in html
        assert "<html lang=\"en\">" in html
        assert "<title>Sales Report</title>" in html
        assert "<h1>Sales Report</h1>" in html
        assert "<h2>Transactions</h2>" in html
        assert "<h2 class=\"summary\">Product Summary</h2>" in html

        # All products present
        assert "<td>A</td>" in html
        assert "<td>B</td>" in html
        assert "<td>C</td>" in html

        # Total row
        assert "<strong>Total</strong>" in html

        # Deterministic: sorted by date then product
        rows_in_html = html.count("<tr>")
        # header row + 6 data rows + 1 total row + 4 summary rows = 12
        assert rows_in_html >= 10, f"Expected at least 10 <tr> blocks, got {rows_in_html}"


def test_normal_input_has_correct_totals():
    """Totals are computed from the data, not hard-coded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "sales.csv")
        html_path = os.path.join(tmpdir, "out.html")
        _write_csv(csv_path, VALID_CSV_LINES)

        rc, _, stderr = _run(csv_path, html_path)
        assert rc == 0, f"Exit code: {rc}. stderr: {stderr}"

        # Compute expected totals from the fixture data
        expected_units = 10 + 4 + 12 + 2 + 5 + 8  # 41
        expected_revenue = 100 + 80 + 120 + 100 + 100 + 80  # 580

        html = _read_output(html_path)
        assert f"<strong>{expected_units}</strong>" in html, (
            f"Expected total units {expected_units} not found in HTML."
        )
        assert f"<strong>{expected_revenue:.2f}</strong>" in html, (
            f"Expected total revenue {expected_revenue:.2f} not found in HTML."
        )


def test_normal_input_different_data():
    """Tool works with different valid CSV data (not just the fixture)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "sales.csv")
        html_path = os.path.join(tmpdir, "out.html")
        # 3 rows, 2 products
        alt_lines = [
            "date,product,units,revenue",
            "2025-01-10,Widget,5,50",
            "2025-01-20,Gadget,3,30",
            "2025-02-01,Widget,7,70",
        ]
        _write_csv(csv_path, alt_lines)

        rc, _, stderr = _run(csv_path, html_path)
        assert rc == 0, f"Exit code: {rc}. stderr: {stderr}"

        html = _read_output(html_path)
        assert "<td>Widget</td>" in html
        assert "<td>Gadget</td>" in html
        # totals: units=15, revenue=150
        assert "<strong>15</strong>" in html
        assert "<strong>150.00</strong>" in html


def test_failure_missing_file():
    """Non-existent input file returns non-zero exit code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "out.html")
        rc, _, stderr = _run("/nonexistent/path/data.csv", html_path)

        assert rc != 0, "Expected non-zero exit code for missing input file."
        assert "not found" in stderr.lower(), f"stderr should mention 'not found': {stderr}"


def test_failure_invalid_header():
    """CSV with wrong/missing headers returns non-zero exit code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "bad.csv")
        html_path = os.path.join(tmpdir, "out.html")
        _write_csv(csv_path, [
            "date,product,quantity,revenue",  # 'quantity' instead of 'units'
            "2026-01-01,X,1,10",
        ])

        rc, _, stderr = _run(csv_path, html_path)

        assert rc != 0, "Expected non-zero exit code for bad headers."
        assert "missing" in stderr.lower() or "header" in stderr.lower(), (
            f"stderr should mention missing header: {stderr}"
        )


def test_failure_bad_units():
    """CSV with non-integer 'units' returns non-zero exit code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "bad_units.csv")
        html_path = os.path.join(tmpdir, "out.html")
        _write_csv(csv_path, [
            "date,product,units,revenue",
            "2026-01-01,X,abc,10",
        ])

        rc, _, stderr = _run(csv_path, html_path)

        assert rc != 0, "Expected non-zero exit code for bad units."
        assert "units" in stderr.lower(), f"stderr should mention 'units': {stderr}"


def test_failure_wrong_column_count():
    """CSV row with wrong number of columns returns non-zero exit code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "bad_cols.csv")
        html_path = os.path.join(tmpdir, "out.html")
        _write_csv(csv_path, [
            "date,product,units,revenue",
            "2026-01-01,X,10",  # missing revenue
        ])

        rc, _, stderr = _run(csv_path, html_path)

        assert rc != 0, "Expected non-zero exit code for wrong column count."
        assert "column" in stderr.lower() or "line" in stderr.lower(), (
            f"stderr should mention column/line: {stderr}"
        )


def test_help_shows_usage():
    """--help flag prints usage information and exits 0."""
    result = subprocess.run(
        [sys.executable, SCRIPT, "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "--help should exit 0"
    output = result.stdout
    assert "input" in output.lower() or "-i" in output
    assert "output" in output.lower() or "-o" in output


def test_no_args_returns_nonzero():
    """Running without arguments returns non-zero exit code."""
    result = subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "Expected non-zero exit code with no arguments."


if __name__ == "__main__":
    # Run all test_ functions
    import traceback
    failures = 0
    passed = 0
    for name, obj in sorted(globals().items()):
        if name.startswith("test_") and callable(obj):
            try:
                obj()
                print(f"  PASS: {name}")
                passed += 1
            except AssertionError as e:
                print(f"  FAIL: {name} — {e}")
                traceback.print_exc()
                failures += 1
            except Exception as e:
                print(f"  ERROR: {name} — {e}")
                traceback.print_exc()
                failures += 1

    print(f"\n{passed} passed, {failures} failed out of {passed + failures} tests")
    sys.exit(1 if failures else 0)
