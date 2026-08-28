from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .config_traversal import (
    ConfigTraversalPressure,
    check_config_traversal_variant,
    generate_config_traversal_variant,
)
from .expense import ExpensePressure, check_expense_variant, generate_expense_variant
from .stateful_world import (
    StatefulWorldPressure,
    check_stateful_world_variant,
    generate_stateful_world_variant,
)


FAMILIES = {"expense_report", "config_traversal", "stateful_world"}


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
    if family == "config_traversal":
        pressure = ConfigTraversalPressure.from_mapping(parameters or {})
        return generate_config_traversal_variant(workspace, seed=int(seed), pressure=pressure)
    if family == "stateful_world":
        pressure = StatefulWorldPressure.from_mapping(parameters or {})
        return generate_stateful_world_variant(workspace, seed=int(seed), pressure=pressure)
    raise ValueError(f"unknown parametric family: {family}")


def check_variant(family: str, workspace: Path, oracle: Mapping[str, Any]) -> tuple[bool, str]:
    if family == "expense_report":
        return check_expense_variant(workspace, oracle)
    if family == "config_traversal":
        return check_config_traversal_variant(workspace, oracle)
    if family == "stateful_world":
        return check_stateful_world_variant(workspace, oracle)
    return False, f"unknown parametric family: {family}"


__all__ = [
    "ConfigTraversalPressure",
    "ExpensePressure",
    "StatefulWorldPressure",
    "FAMILIES",
    "check_variant",
    "materialize_variant",
]
