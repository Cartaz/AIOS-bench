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
from .coverage_migration import (
    CoverageMigrationPressure,
    evaluate_coverage_migration_variant,
    generate_coverage_migration_variant,
)
from .expense import ExpensePressure, check_expense_variant, generate_expense_variant
from .greenfield_registry import (
    GreenfieldRegistryPressure,
    evaluate_greenfield_registry_variant,
    generate_greenfield_registry_variant,
)
from .pristine_refactor import (
    PristineRefactorPressure,
    evaluate_pristine_refactor_variant,
    generate_pristine_refactor_variant,
)
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
    "coverage_migration",
    "pristine_refactor",
    "greenfield_registry",
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
    if family == "coverage_migration":
        pressure = CoverageMigrationPressure.from_mapping(parameters or {})
        return generate_coverage_migration_variant(workspace, seed=int(seed), pressure=pressure)
    if family == "pristine_refactor":
        pressure = PristineRefactorPressure.from_mapping(parameters or {})
        return generate_pristine_refactor_variant(workspace, seed=int(seed), pressure=pressure)
    if family == "greenfield_registry":
        pressure = GreenfieldRegistryPressure.from_mapping(parameters or {})
        return generate_greenfield_registry_variant(workspace, seed=int(seed), pressure=pressure)
    raise ValueError(f"unknown parametric family: {family}")


def evaluate_variant(
    family: str,
    workspace: Path,
    oracle: Mapping[str, Any],
) -> dict[str, Any]:
    if family == "coverage_migration":
        return evaluate_coverage_migration_variant(workspace, oracle)
    if family == "pristine_refactor":
        return evaluate_pristine_refactor_variant(workspace, oracle)
    if family == "greenfield_registry":
        return evaluate_greenfield_registry_variant(workspace, oracle)

    checks = {
        "expense_report": check_expense_variant,
        "config_traversal": check_config_traversal_variant,
        "causal_gateway": check_causal_gateway_variant,
        "runtime_investigation": check_runtime_investigation_variant,
        "tool_branching": check_tool_branching_variant,
    }
    checker = checks.get(family)
    if checker is None:
        return {"passed": False, "detail": f"unknown parametric family: {family}"}
    passed, detail = checker(workspace, oracle)
    return {"passed": bool(passed), "detail": str(detail)}


def check_variant(family: str, workspace: Path, oracle: Mapping[str, Any]) -> tuple[bool, str]:
    result = evaluate_variant(family, workspace, oracle)
    return bool(result["passed"]), str(result.get("detail", ""))


__all__ = [
    "CausalGatewayPressure",
    "ConfigTraversalPressure",
    "CoverageMigrationPressure",
    "ExpensePressure",
    "GreenfieldRegistryPressure",
    "PristineRefactorPressure",
    "RuntimeInvestigationPressure",
    "ToolBranchingPressure",
    "FAMILIES",
    "check_variant",
    "evaluate_variant",
    "materialize_variant",
]
