from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .expense import ExpensePressure, check_expense_variant, generate_expense_variant


FAMILIES = {"expense_report"}


def materialize_variant(
    family: str,
    workspace: Path,
    *,
    seed: int,
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if family == "expense_report":
        pressure = ExpensePressure.from_mapping(parameters or {})
        return generate_expense_variant(workspace, seed=int(seed), pressure=pressure)
    raise ValueError(f"unknown parametric family: {family}")


def check_variant(family: str, workspace: Path, oracle: Mapping[str, Any]) -> tuple[bool, str]:
    if family == "expense_report":
        return check_expense_variant(workspace, oracle)
    return False, f"unknown parametric family: {family}"


__all__ = [
    "ExpensePressure",
    "FAMILIES",
    "check_variant",
    "materialize_variant",
]
