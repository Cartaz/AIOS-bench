from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .causal_gateway import (
    CausalGatewayPressure,
    check_causal_gateway_variant,
    generate_causal_gateway_variant,
)
from .config_traversal import (
    ConfigTraversalPressure,
    check_config_traversal_variant,
    generate_config_traversal_variant,
)
from .expense import ExpensePressure, check_expense_variant, generate_expense_variant
from .runtime_investigation import (
    RuntimeInvestigationPressure,
    check_runtime_investigation_variant,
    generate_runtime_investigation_variant,
)
from .tool_branching import (
    ToolBranchingPressure,
    check_tool_branching_variant,
    generate_tool_branching_variant,
)


FAMILIES = {
    "expense_report",
    "config_traversal",
    "causal_gateway",
    "runtime_investigation",
    "tool_branching",
}


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
    if family == "causal_gateway":
        pressure = CausalGatewayPressure.from_mapping(parameters or {})
        return generate_causal_gateway_variant(workspace, seed=int(seed), pressure=pressure)
    if family == "runtime_investigation":
        pressure = RuntimeInvestigationPressure.from_mapping(parameters or {})
        return generate_runtime_investigation_variant(workspace, seed=int(seed), pressure=pressure)
    if family == "tool_branching":
        pressure = ToolBranchingPressure.from_mapping(parameters or {})
        return generate_tool_branching_variant(workspace, seed=int(seed), pressure=pressure)
    raise ValueError(f"unknown parametric family: {family}")


def check_variant(family: str, workspace: Path, oracle: Mapping[str, Any]) -> tuple[bool, str]:
    if family == "expense_report":
        return check_expense_variant(workspace, oracle)
    if family == "config_traversal":
        return check_config_traversal_variant(workspace, oracle)
    if family == "causal_gateway":
        return check_causal_gateway_variant(workspace, oracle)
    if family == "runtime_investigation":
        return check_runtime_investigation_variant(workspace, oracle)
    if family == "tool_branching":
        return check_tool_branching_variant(workspace, oracle)
    return False, f"unknown parametric family: {family}"


__all__ = [
    "CausalGatewayPressure",
    "ConfigTraversalPressure",
    "ExpensePressure",
    "RuntimeInvestigationPressure",
    "ToolBranchingPressure",
    "FAMILIES",
    "check_variant",
    "materialize_variant",
]
