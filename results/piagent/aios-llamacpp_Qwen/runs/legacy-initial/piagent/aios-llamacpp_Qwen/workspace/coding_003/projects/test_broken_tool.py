"""Tests for the monthly_total tool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project root is importable.
_project_root = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(_project_root))

from broken_tool import monthly_total  # noqa: E402


class TestMonthlyTotal:
    """Tests for :func:`monthly_total`."""

    def test_sum_of_integers(self) -> None:
        assert monthly_total([1, 2, 3]) == 6.0

    def test_sum_of_floats(self) -> None:
        assert monthly_total([1.5, 2.5, 3.0]) == 7.0

    def test_empty_list(self) -> None:
        assert monthly_total([]) == 0.0

    def test_negative_values(self) -> None:
        assert monthly_total([-10, 20, -5]) == 5.0

    def test_single_value(self) -> None:
        assert monthly_total([42]) == 42.0

    def test_string_numbers(self) -> None:
        assert monthly_total(["10", "20", "30"]) == 60.0

    def test_mixed_types(self) -> None:
        assert monthly_total([10, 20, "30"]) == 60.0

    def test_return_type_is_float(self) -> None:
        result = monthly_total([1, 2, 3])
        assert isinstance(result, float)
