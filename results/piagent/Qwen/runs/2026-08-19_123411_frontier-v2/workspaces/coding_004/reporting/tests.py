"""
Test suite for the CSV reporting utility.

Covers:
  - Valid expense and sales datasets
  - Malformed rows (bad dates, non-numeric amounts, missing fields)
  - Empty datasets (empty file, header-only file)
  - Unrecognised schemas
  - Deterministic output ordering
  - CLI error exit codes
"""

import csv
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main as unittest_main

# Make sure the project root is importable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from decimal import Decimal

from reporting.loader import parse_csv_string, parse_csv_text, parse_csv_file
from reporting.records import (
    Category,
    EmptyDatasetError,
    ExpenseRecord,
    InvalidDatasetError,
    RecordError,
    SalesRecord,
    _detect_schema,
)
from reporting.report import (
    generate_expense_report,
    generate_sales_report,
    generate_report,
)


# ===========================================================================
# Schema detection
# ===========================================================================

class TestSchemaDetection(TestCase):
    def test_expense_schema(self):
        header = ["date", "category", "description", "amount"]
        self.assertEqual(_detect_schema(header), "expense")

    def test_sales_schema(self):
        header = ["date", "product", "units", "revenue"]
        self.assertEqual(_detect_schema(header), "sales")

    def test_case_insensitive(self):
        header = ["Date", "CATEGORY", "DESCRIPTION", "Amount"]
        self.assertEqual(_detect_schema(header), "expense")

    def test_unrecognised_schema(self):
        header = ["foo", "bar"]
        with self.assertRaises(InvalidDatasetError):
            _detect_schema(header)

    def test_partial_overlap(self):
        header = ["date", "category", "description"]
        with self.assertRaises(InvalidDatasetError):
            _detect_schema(header)


# ===========================================================================
# ExpenseRecord validation
# ===========================================================================

class TestExpenseRecord(TestCase):
    def _row(self, **overrides):
        defaults = {
            "date": "2026-07-15",
            "category": "software",
            "description": "Test item",
            "amount": "19.99",
        }
        defaults.update(overrides)
        return defaults

    def test_valid_expense(self):
        rec = ExpenseRecord.from_row(self._row(), row_index=1)
        self.assertEqual(rec.date.isoformat(), "2026-07-15")
        self.assertEqual(rec.category, Category.SOFTWARE)
        self.assertEqual(rec.amount, Decimal("19.99"))

    def test_unknown_category(self):
        rec = ExpenseRecord.from_row(self._row(category="misc"), row_index=1)
        self.assertEqual(rec.category, Category.UNKNOWN)

    def test_invalid_date(self):
        with self.assertRaises(RecordError) as ctx:
            ExpenseRecord.from_row(self._row(date="not-a-date"), row_index=5)
        self.assertIn("Invalid date", str(ctx.exception))
        self.assertEqual(ctx.exception.row, 5)

    def test_negative_amount(self):
        with self.assertRaises(RecordError) as ctx:
            ExpenseRecord.from_row(self._row(amount="-5.00"), row_index=3)
        self.assertIn("non-negative", str(ctx.exception))
        self.assertEqual(ctx.exception.column, "amount")

    def test_non_numeric_amount(self):
        with self.assertRaises(RecordError):
            ExpenseRecord.from_row(self._row(amount="abc"), row_index=2)

    def test_empty_description(self):
        with self.assertRaises(RecordError):
            ExpenseRecord.from_row(self._row(description=""), row_index=4)

    def test_missing_column(self):
        row = {"date": "2026-07-01", "category": "office"}
        with self.assertRaises(RecordError) as ctx:
            ExpenseRecord.from_row(row, row_index=0)
        self.assertIn("Missing required columns", str(ctx.exception))

    def test_zero_amount_is_valid(self):
        rec = ExpenseRecord.from_row(self._row(amount="0"), row_index=1)
        self.assertEqual(rec.amount, 0)


# ===========================================================================
# SalesRecord validation
# ===========================================================================

class TestSalesRecord(TestCase):
    def _row(self, **overrides):
        defaults = {
            "date": "2026-07-15",
            "product": "X",
            "units": "10",
            "revenue": "100",
        }
        defaults.update(overrides)
        return defaults

    def test_valid_sale(self):
        rec = SalesRecord.from_row(self._row(), row_index=1)
        self.assertEqual(rec.units, 10)
        self.assertEqual(rec.revenue, 100)

    def test_invalid_units(self):
        with self.assertRaises(RecordError):
            SalesRecord.from_row(self._row(units="abc"), row_index=2)

    def test_negative_units(self):
        with self.assertRaises(RecordError) as ctx:
            SalesRecord.from_row(self._row(units="-3"), row_index=1)
        self.assertEqual(ctx.exception.column, "units")

    def test_invalid_revenue(self):
        with self.assertRaises(RecordError):
            SalesRecord.from_row(self._row(revenue="xyz"), row_index=3)

    def test_empty_product(self):
        with self.assertRaises(RecordError):
            SalesRecord.from_row(self._row(product=""), row_index=1)

    def test_missing_column(self):
        with self.assertRaises(RecordError):
            SalesRecord.from_row({"date": "2026-07-01"}, row_index=0)


# ===========================================================================
# Loader — valid CSV
# ===========================================================================

class TestLoaderValid(TestCase):
    def test_expense_csv(self):
        schema, records = parse_csv_string(EXPENSE_SAMPLE)
        self.assertEqual(schema, "expense")
        self.assertEqual(len(records), 3)
        self.assertIsInstance(records[0], ExpenseRecord)

    def test_sales_csv(self):
        schema, records = parse_csv_string(SALES_SAMPLE)
        self.assertEqual(schema, "sales")
        self.assertEqual(len(records), 2)
        self.assertIsInstance(records[0], SalesRecord)


# ===========================================================================
# Loader — malformed rows
# ===========================================================================

class TestLoaderMalformed(TestCase):
    def test_bad_date(self):
        text = "date,category,description,amount\nbad-date,software,Test,10"
        with self.assertRaises(RecordError):
            parse_csv_string(text)

    def test_bad_amount(self):
        text = "date,category,description,amount\n2026-01-01,software,Test,not-a-number"
        with self.assertRaises(RecordError):
            parse_csv_string(text)

    def test_multiple_errors_reported_first(self):
        text = (
            "date,category,description,amount\n"
            "bad-date,software,Test,10\n"
            "2026-01-01,office,Test,abc\n"
        )
        with self.assertRaises(RecordError) as ctx:
            parse_csv_string(text)
        self.assertIn("and 1 more errors", str(ctx.exception))
        self.assertEqual(ctx.exception.row, 1)  # first bad row

    def test_empty_category(self):
        text = "date,category,description,amount\n2026-01-01,,Test,10"
        with self.assertRaises(RecordError):
            parse_csv_string(text)


# ===========================================================================
# Loader — empty / header-only datasets
# ===========================================================================

class TestLoaderEmpty(TestCase):
    def test_completely_empty(self):
        with self.assertRaises(EmptyDatasetError):
            parse_csv_string("")

    def test_header_only(self):
        with self.assertRaises(EmptyDatasetError):
            parse_csv_string("date,category,description,amount\n")

    def test_empty_sales(self):
        with self.assertRaises(EmptyDatasetError):
            parse_csv_string("date,product,units,revenue\n")


# ===========================================================================
# Report generation — determinism
# ===========================================================================

class TestReportDeterminism(TestCase):
    def test_expense_report_sorted(self):
        _, records = parse_csv_string(EXPENSE_SAMPLE)
        report1 = generate_expense_report(records)
        report2 = generate_expense_report(records)
        self.assertEqual(report1, report2)

    def test_sales_report_sorted(self):
        _, records = parse_csv_string(SALES_SAMPLE)
        report1 = generate_sales_report(records)
        report2 = generate_sales_report(records)
        self.assertEqual(report1, report2)

    def test_report_contains_summary(self):
        schema, records = parse_csv_string(EXPENSE_SAMPLE)
        content = generate_report(schema, records)
        self.assertIn("## Summary", content)
        self.assertIn("Total records:", content)


# ===========================================================================
# Report generation — dispatch
# ===========================================================================

class TestReportDispatch(TestCase):
    def test_expense_dispatch(self):
        schema, records = parse_csv_string(EXPENSE_SAMPLE)
        content = generate_report(schema, records)
        self.assertIn("Expense Report", content)

    def test_sales_dispatch(self):
        schema, records = parse_csv_string(SALES_SAMPLE)
        content = generate_report(schema, records)
        self.assertIn("Sales Report", content)

    def test_unknown_schema(self):
        with self.assertRaises(ValueError):
            generate_report("unknown", [])


# ===========================================================================
# File-based loader
# ===========================================================================

class TestFileLoader(TestCase):
    def test_nonexistent_file(self):
        with self.assertRaises(FileNotFoundError):
            parse_csv_file("/tmp/this_file_does_not_exist_12345.csv")

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            with self.assertRaises(EmptyDatasetError):
                parse_csv_file(path)
        finally:
            os.unlink(path)

    def test_real_expense_file(self):
        data_dir = ROOT / "data"
        schema, records = parse_csv_file(data_dir / "expenses.csv")
        self.assertEqual(schema, "expense")
        self.assertGreater(len(records), 0)

    def test_real_sales_file(self):
        data_dir = ROOT / "data"
        schema, records = parse_csv_file(data_dir / "sales.csv")
        self.assertEqual(schema, "sales")
        self.assertGreater(len(records), 0)


# ===========================================================================
# CLI tests
# ===========================================================================

class TestCLI(TestCase):
    def test_cli_success(self):
        data_dir = ROOT / "data"
        result = subprocess.run(
            [sys.executable, "-m", "reporting.main", str(data_dir / "expenses.csv",)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Report saved", result.stdout)

    def test_cli_missing_file(self):
        result = subprocess.run(
            [sys.executable, "-m", "reporting.main", "/nonexistent/file.csv"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stderr)

    def test_cli_malformed_csv(self):
        # Create a temp malformed CSV
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp.write("date,category,description,amount\nbad-date,software,Test,abc\n")
            path = tmp.name
        try:
            result = subprocess.run(
                [sys.executable, "-m", "reporting.main", path],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("VALIDATION ERROR", result.stderr)
        finally:
            os.unlink(path)

    def test_cli_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp.write("date,category,description,amount\n")
            path = tmp.name
        try:
            result = subprocess.run(
                [sys.executable, "-m", "reporting.main", path],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("VALIDATION ERROR", result.stderr)
        finally:
            os.unlink(path)


# ===========================================================================
# Fixtures
# ===========================================================================

EXPENSE_SAMPLE = (
    "date,category,description,amount\n"
    "2026-07-01,software,Editor,19.99\n"
    "2026-07-03,office,Notebook,4.50\n"
    "2026-07-08,software,Cloud storage,9.99\n"
)

SALES_SAMPLE = (
    "date,product,units,revenue\n"
    "2026-07-01,A,10,100\n"
    "2026-07-03,B,4,80\n"
)


if __name__ == "__main__":
    unittest_main()
