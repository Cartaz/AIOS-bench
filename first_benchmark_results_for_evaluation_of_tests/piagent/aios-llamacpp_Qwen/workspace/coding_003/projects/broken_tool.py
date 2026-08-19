"""Provide a simple monthly-total calculator for numeric values."""

from __future__ import annotations


def monthly_total(values: list[float | int]) -> float:
    """Return the sum of *values*.

    Raises
    ------
    TypeError
        If any element of *values* cannot be interpreted as a number.
    """
    total = 0.0
    for value in values:
        total += float(value)
    return total


if __name__ == "__main__":
    print(monthly_total([10, 20, "30"]))
