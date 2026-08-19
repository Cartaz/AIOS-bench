"""Report module – formats and prints results."""

from __future__ import annotations

import math
from typing import Sequence


def format_total(values: Sequence[float], total: float) -> str:
    """Return a human-readable summary string."""
    count = len(values)
    average = total / count if count else 0.0
    return (
        f"monthly_total({list(values)}) = {total:.2f}  "
        f"(n={count}, avg={average:.2f})"
    )


def print_report(values: Sequence[float], total: float) -> None:
    """Print the formatted summary to stdout."""
    print(format_total(values, total))


def write_report(values: Sequence[float], total: float, path: str) -> None:
    """Write the report to a file."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(format_total(values, total) + "\n")
