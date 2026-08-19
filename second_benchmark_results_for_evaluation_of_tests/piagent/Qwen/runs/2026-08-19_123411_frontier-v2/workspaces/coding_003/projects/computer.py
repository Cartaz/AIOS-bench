"""Computation module – pure calculation functions."""

from __future__ import annotations


def compute_total(values: list[float]) -> float:
    """Return the sum of a list of numbers.

    This is deliberately a separate module from parsing/validation so that
    downstream callers can reuse the logic with their own data sources.
    """
    total = 0.0
    for value in values:
        total += value
    return total
