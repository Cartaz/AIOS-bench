"""Validation module – checks parsed data for integrity before computation."""

from __future__ import annotations

from typing import Sequence


class ValidationError(Exception):
    """Raised when validation rules are violated."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def validate_values(values: Sequence[float]) -> list[float]:
    """Validate a list of parsed numeric values.

    Rules:
      1. Input must be a sequence (list/tuple) — not a scalar or None.
      2. All elements must be finite numbers (reject NaN / Inf).
      3. The list must not be empty.

    Returns the validated list on success.
    Raises ValidationError on failure.
    """
    if not isinstance(values, (list, tuple)):
        raise ValidationError("Input must be a sequence of values")

    if len(values) == 0:
        raise ValidationError("Cannot compute monthly total: no values provided")

    for i, val in enumerate(values):
        if not isinstance(val, (int, float)):
            raise ValidationError(f"Value at index {i} is not numeric: {val!r}")
        if val != val:  # NaN check
            raise ValidationError(f"Value at index {i} is NaN")
        if val == float("inf") or val == float("-inf"):
            raise ValidationError(f"Value at index {i} is infinite")

    return list(values)  # return a copy so the caller cannot mutate internals
