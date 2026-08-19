"""Comprehensive tests for the refactored monthly-total tool.

Covers parsing, validation, computation, reporting, and CLI behaviour
including edge cases (empty data, NaN, Inf, mixed types, invalid CSV, etc.).
"""

from __future__ import annotations

import csv
import io
import os
import tempfile
from pathlib import Path

import pytest

# The project directory is on sys.path because tests run from there.
import parser as parse_mod
import validator as val_mod
import computer as comp_mod
import reporter as rep_mod
import broken_tool as tool_mod

# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestParseValues:
    def test_mixed_types(self):
        result = parse_mod.parse_values([10, 20, "30"])
        assert result == [10.0, 20.0, 30.0]

    def test_all_floats(self):
        assert parse_mod.parse_values([1.5, 2.5]) == [1.5, 2.5]

    def test_all_strings(self):
        assert parse_mod.parse_values(["1", "2", "3"]) == [1.0, 2.0, 3.0]

    def test_negative_numbers(self):
        assert parse_mod.parse_values([-10, "5", -3.0]) == [-10.0, 5.0, -3.0]

    def test_empty_string_skipped(self):
        result = parse_mod.parse_values([10, "", "  ", 20])
        assert result == [10.0, 20.0]

    def test_non_numeric_strings_skipped(self):
        result = parse_mod.parse_values([10, "abc", 20])
        assert result == [10.0, 20.0]

    def test_all_invalid_returns_empty_list(self):
        result = parse_mod.parse_values(["abc", "xyz"])
        assert result == []

    def test_none_input_returns_none(self):
        assert parse_mod.parse_values(None) is None

    def test_string_input_returns_none(self):
        assert parse_mod.parse_values("not a list") is None

    def test_empty_list(self):
        result = parse_mod.parse_values([])
        assert result == []

    def test_zero_values(self):
        result = parse_mod.parse_values([0, "0", 0.0])
        assert result == [0.0, 0.0, 0.0]

    def test_large_numbers(self):
        result = parse_mod.parse_values([1e10, "1e10"])
        assert result == [1e10, 1e10]

    def test_negative_strings(self):
        result = parse_mod.parse_values(["-5", "-3.5"])
        assert result == [-5.0, -3.5]

    def test_tuple_input(self):
        result = parse_mod.parse_values((1, 2, 3))
        assert result == [1.0, 2.0, 3.0]


class TestParseCSV:
    def test_valid_csv(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as fh:
            fh.write("date,amount\n2026-01-01,10\n2026-01-02,20\n")
            name = fh.name
        try:
            result = parse_mod.parse_csv(name)
            assert result == [10.0, 20.0]
        finally:
            os.unlink(name)

    def test_csv_with_non_numeric_skipped(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as fh:
            fh.write("date,amount\n2026-01-01,10\n2026-01-02,abc\n")
            name = fh.name
        try:
            result = parse_mod.parse_csv(name)
            assert result == [10.0]
        finally:
            os.unlink(name)

    def test_missing_amount_column(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as fh:
            fh.write("date,revenue\n2026-01-01,10\n")
            name = fh.name
        try:
            result = parse_mod.parse_csv(name)
            assert result is None
        finally:
            os.unlink(name)

    def test_nonexistent_file(self):
        assert parse_mod.parse_csv("/no/such/file.csv") is None

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as fh:
            name = fh.name
        try:
            result = parse_mod.parse_csv(name)
            assert result is None
        finally:
            os.unlink(name)

    def test_csv_only_header(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as fh:
            fh.write("date,amount\n")
            name = fh.name
        try:
            result = parse_mod.parse_csv(name)
            assert result is None
        finally:
            os.unlink(name)


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------

class TestValidateValues:
    def test_valid_list(self):
        result = val_mod.validate_values([1.0, 2.0])
        assert result == [1.0, 2.0]

    def test_empty_raises(self):
        with pytest.raises(val_mod.ValidationError, match="no values"):
            val_mod.validate_values([])

    def test_none_raises(self):
        with pytest.raises(val_mod.ValidationError):
            val_mod.validate_values(None)  # type: ignore[arg-type]

    def test_string_raises(self):
        with pytest.raises(val_mod.ValidationError):
            val_mod.validate_values("not a list")  # type: ignore[arg-type]

    def test_nan_raises(self):
        import math
        with pytest.raises(val_mod.ValidationError, match="NaN"):
            val_mod.validate_values([float("nan")])

    def test_inf_raises(self):
        with pytest.raises(val_mod.ValidationError, match="infinite"):
            val_mod.validate_values([float("inf")])

    def test_negative_inf_raises(self):
        with pytest.raises(val_mod.ValidationError, match="infinite"):
            val_mod.validate_values([float("-inf")])

    def test_single_value(self):
        result = val_mod.validate_values([42.0])
        assert result == [42.0]

    def test_returns_copy(self):
        original = [1.0, 2.0]
        result = val_mod.validate_values(original)
        result[0] = 999.0
        assert original[0] == 1.0  # original unchanged


# ---------------------------------------------------------------------------
# Computer tests
# ---------------------------------------------------------------------------

class TestComputeTotal:
    def test_simple_sum(self):
        assert comp_mod.compute_total([10.0, 20.0, 30.0]) == 60.0

    def test_floats(self):
        result = comp_mod.compute_total([1.1, 2.2, 3.3])
        assert abs(result - 6.6) < 1e-9

    def test_negative_values(self):
        assert comp_mod.compute_total([-10, 10]) == 0.0

    def test_single_value(self):
        assert comp_mod.compute_total([42.0]) == 42.0

    def test_empty_list(self):
        assert comp_mod.compute_total([]) == 0.0

    def test_large_values(self):
        assert comp_mod.compute_total([1e15, 1e15]) == 2e15


# ---------------------------------------------------------------------------
# Reporter tests
# ---------------------------------------------------------------------------

class TestReporter:
    def test_format_total(self, capsys):
        out = rep_mod.format_total([10.0, 20.0], 30.0)
        assert "30.00" in out
        assert "n=2" in out
        assert "avg=15.00" in out

    def test_print_report(self, capsys):
        rep_mod.print_report([10.0], 10.0)
        captured = capsys.readouterr()
        assert "10.00" in captured.out

    def test_write_report(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as fh:
            name = fh.name
        try:
            rep_mod.write_report([5.0], 5.0, name)
            content = Path(name).read_text(encoding="utf-8")
            assert "5.00" in content
        finally:
            os.unlink(name)


# ---------------------------------------------------------------------------
# Integration / CLI tests
# ---------------------------------------------------------------------------

class TestMonthlyTotalWrapper:
    def test_default_mixed(self):
        result = tool_mod.monthly_total([10, 20, "30"])
        assert result == 60.0

    def test_all_valid(self):
        result = tool_mod.monthly_total([1, 2, 3])
        assert result == 6.0

    def test_all_invalid_returns_none(self):
        result = tool_mod.monthly_total(["abc"])
        assert result is None

    def test_none_input_returns_none(self):
        result = tool_mod.monthly_total(None)
        assert result is None


class TestCLI:
    def test_default_no_args(self, capsys):
        ret = tool_mod.main([])
        assert ret == 0
        captured = capsys.readouterr()
        assert "60.00" in captured.out

    def test_custom_values(self, capsys):
        ret = tool_mod.main(["--values", "5", "10", "15"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "30.00" in captured.out

    def test_csv_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as fh:
            fh.write("date,amount\n2026-01-01,100\n2026-01-02,200\n")
            name = fh.name
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False
            ) as fh2:
                out = fh2.name
            ret = tool_mod.main(["--csv", name, "--file", out])
            assert ret == 0
            assert Path(out).read_text().strip() == "monthly_total([100.0, 200.0]) = 300.00  (n=2, avg=150.00)"
        finally:
            os.unlink(name)
            os.unlink(out)

    def test_csv_nonexistent(self, capsys):
        ret = tool_mod.main(["--csv", "/no/such/file.csv"])
        assert ret == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    def test_no_valid_values(self, capsys):
        ret = tool_mod.main(["--values", "abc", "xyz"])
        assert ret == 1
        captured = capsys.readouterr()
        assert "error" in captured.err.lower()

    def test_file_output(self, capsys):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as fh:
            out = fh.name
        try:
            ret = tool_mod.main(["--values", "10", "20", "--file", out])
            assert ret == 0
            content = Path(out).read_text()
            assert "30.00" in content
        finally:
            os.unlink(out)
