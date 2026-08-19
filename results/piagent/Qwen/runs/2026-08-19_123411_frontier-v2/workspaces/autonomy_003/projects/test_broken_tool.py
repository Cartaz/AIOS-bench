"""Tests for monthly_total — regression and coverage suite."""

from broken_tool import monthly_total


class TestMonthlyTotal:
    """Test the monthly_total function for correctness and robustness."""

    def test_simple_integers(self):
        """Basic integer list sums correctly."""
        assert monthly_total([10, 20, 30]) == 60

    def test_mixed_integers(self):
        """Mixed integer inputs sum correctly."""
        assert monthly_total([10, 20, "30"]) == 60

    def test_empty_list(self):
        """An empty list returns zero."""
        assert monthly_total([]) == 0

    def test_single_value(self):
        """A single value returns that value as a number."""
        assert monthly_total([42]) == 42

    def test_single_string_number(self):
        """A single numeric string returns as a number."""
        assert monthly_total(["30"]) == 30

    def test_floats(self):
        """Float values are summed correctly."""
        assert monthly_total([1.5, 2.5, 3.0]) == 7.0

    def test_mixed_int_float(self):
        """Mixed int and float values sum correctly."""
        result = monthly_total([10, 20.5])
        assert result == 30.5

    def test_negative_values(self):
        """Negative values are handled correctly."""
        assert monthly_total([10, -5, 3]) == 8

    def test_string_and_float(self):
        """String numbers and floats mix correctly."""
        result = monthly_total([10, "20.5", 30])
        assert result == 60.5

    def test_all_string_numbers(self):
        """All-string numeric list sums correctly."""
        assert monthly_total(["1", "2", "3"]) == 6

    def test_zero(self):
        """Zero (int) is handled correctly."""
        assert monthly_total([0, 10]) == 10

    def test_zero_string(self):
        """Zero string is handled correctly."""
        assert monthly_total(["0", "10"]) == 10

    def test_large_values(self):
        """Large numbers are handled correctly."""
        assert monthly_total([1_000_000, 2_000_000]) == 3_000_000

    def test_result_is_number(self):
        """Result should always be a number (int or float), never a string."""
        result = monthly_total([10, 20, "30"])
        assert isinstance(result, (int, float))
