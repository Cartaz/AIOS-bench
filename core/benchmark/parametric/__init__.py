from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ..task_runtime import TaskRuntime
from ..tool_recovery_api import (
    start_tool_recovery_runtime,
    write_tool_recovery_client,
)
from ..tool_recovery_service import (
    diagnose_tool_recovery_failure,
    verify_tool_recovery_log,
)
from ..world_api import (
    start_dependency_world_runtime,
    start_support_world_runtime,
    write_world_api_client,
)
from ..world_service import (
    SupportDependencyWorldService,
    SupportWorldService,
    verify_support_action_log,
)
from .config_traversal import (
    ConfigTraversalPressure,
    check_config_traversal_variant,
    generate_config_traversal_variant,
)
from .cross_artifact import (
    CrossArtifactPressure,
    generate_cross_artifact_variant,
    grade_cross_artifact_variant,
)
from .dependency_world import (
    DependencyWorldPressure,
    check_dependency_world_variant,
    generate_dependency_world_variant,
)
from .epistemic_twins import (
    EpistemicTwinPressure,
    generate_epistemic_twins_variant,
    grade_epistemic_twins_variant,
)
from .expense import ExpensePressure, check_expense_variant, generate_expense_variant
from .grading import VariantGrade
from .stateful_world import (
    StatefulWorldPressure,
    check_stateful_world_variant,
    generate_stateful_world_variant,
)
from .tool_recovery import (
    ToolRecoveryPressure,
    check_tool_recovery_variant,
    generate_tool_recovery_variant,
)
from .wide_retrieval import (
    WideRetrievalPressure,
    generate_wide_retrieval_variant,
    grade_wide_retrieval_variant,
)
from .workspace_lineage import (
    WorkspaceLineagePressure,
    check_workspace_lineage_variant,
    generate_workspace_lineage_variant,
)


FAMILIES = {
    "expense_report",
    "config_traversal",
    "stateful_world",
    "dependency_world",
    "workspace_lineage",
    "tool_recovery",
    "wide_retrieval",
    "cross_artifact",
    "epistemic_twins",
}

_PRESSURE_TYPES = {
    "expense_report": ExpensePressure,
    "config_traversal": ConfigTraversalPressure,
    "stateful_world": StatefulWorldPressure,
    "dependency_world": DependencyWorldPressure,
    "workspace_lineage": WorkspaceLineagePressure,
    "tool_recovery": ToolRecoveryPressure,
    "wide_retrieval": WideRetrievalPressure,
    "cross_artifact": CrossArtifactPressure,
    "epistemic_twins": EpistemicTwinPressure,
}


def normalize_parameters(
    parameters: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, int]]:
    """Return validated effective coordinates for every registered family.

    Suite manifests record defaults too so execution identity changes whenever
    effective workload semantics change, even when a caller relies on defaults.
    """
    supplied = parameters or {}
    unknown = set(supplied) - FAMILIES
    if unknown:
        raise ValueError(f"unknown parametric families: {sorted(unknown)}")
    return {
        family: pressure_type.from_mapping(supplied.get(family, {})).to_dict()
        for family, pressure_type in _PRESSURE_TYPES.items()
    }


def _reseal_variant(oracle: dict[str, Any]) -> dict[str, Any]:
    core = {key: value for key, value in oracle.items() if key != "variant_digest"}
    payload = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    oracle["variant_digest"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return oracle


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
    if family == "workspace_lineage":
        pressure = WorkspaceLineagePressure.from_mapping(parameters or {})
        return generate_workspace_lineage_variant(workspace, seed=int(seed), pressure=pressure)
    if family == "wide_retrieval":
        pressure = WideRetrievalPressure.from_mapping(parameters or {})
        return generate_wide_retrieval_variant(workspace, seed=int(seed), pressure=pressure)
    if family == "cross_artifact":
        pressure = CrossArtifactPressure.from_mapping(parameters or {})
        return generate_cross_artifact_variant(workspace, seed=int(seed), pressure=pressure)
    if family == "epistemic_twins":
        pressure = EpistemicTwinPressure.from_mapping(parameters or {})
        return generate_epistemic_twins_variant(workspace, seed=int(seed), pressure=pressure)
    if family == "tool_recovery":
        pressure = ToolRecoveryPressure.from_mapping(parameters or {})
        oracle = generate_tool_recovery_variant(
            workspace,
            seed=int(seed),
            pressure=pressure,
        )
        write_tool_recovery_client(workspace)
        return _reseal_variant(oracle)
    if family == "stateful_world":
        pressure = StatefulWorldPressure.from_mapping(parameters or {})
        oracle = generate_stateful_world_variant(workspace, seed=int(seed), pressure=pressure)
        write_world_api_client(workspace)
        oracle["mutation_interface"] = SupportWorldService.contract()
        return _reseal_variant(oracle)
    if family == "dependency_world":
        pressure = DependencyWorldPressure.from_mapping(parameters or {})
        oracle = generate_dependency_world_variant(workspace, seed=int(seed), pressure=pressure)
        write_world_api_client(workspace)
        oracle["mutation_interface"] = SupportDependencyWorldService.contract()
        return _reseal_variant(oracle)
    raise ValueError(f"unknown parametric family: {family}")


def start_variant_runtime(
    family: str,
    workspace: Path,
    *,
    run_dir: Path,
    task_id: str,
    oracle: Mapping[str, Any],
) -> TaskRuntime:
    if family == "stateful_world":
        return start_support_world_runtime(workspace, run_dir, task_id, oracle)
    if family == "dependency_world":
        return start_dependency_world_runtime(workspace, run_dir, task_id, oracle)
    if family == "tool_recovery":
        return start_tool_recovery_runtime(workspace, run_dir, task_id, oracle)
    return TaskRuntime()


def _check_mediated_world(
    family: str,
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None,
    task_id: str | None,
) -> tuple[bool, str]:
    checker = {
        "stateful_world": check_stateful_world_variant,
        "dependency_world": check_dependency_world_variant,
    }[family]
    passed, detail = checker(workspace, oracle)
    if not passed:
        return passed, detail
    provenance_ok, provenance_detail = verify_support_action_log(
        oracle,
        run_dir=run_dir,
        task_id=task_id,
    )
    if not provenance_ok:
        return False, provenance_detail
    return True, f"{detail}; {provenance_detail}"


def _check_tool_recovery(
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None,
    task_id: str | None,
) -> tuple[bool, str]:
    passed, detail = check_tool_recovery_variant(workspace, oracle)
    if not passed:
        return passed, detail
    provenance_ok, provenance_detail = verify_tool_recovery_log(
        oracle,
        run_dir=run_dir,
        task_id=task_id,
    )
    if not provenance_ok:
        return False, provenance_detail
    return True, f"{detail}; {provenance_detail}"


def evaluate_variant(
    family: str,
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None = None,
    task_id: str | None = None,
) -> VariantGrade:
    """Grade one generated family through a common structured contract."""
    if family == "wide_retrieval":
        return grade_wide_retrieval_variant(workspace, oracle)
    if family == "cross_artifact":
        return grade_cross_artifact_variant(workspace, oracle)
    if family == "epistemic_twins":
        return grade_epistemic_twins_variant(workspace, oracle)
    if family == "expense_report":
        passed, detail = check_expense_variant(workspace, oracle)
    elif family == "config_traversal":
        passed, detail = check_config_traversal_variant(workspace, oracle)
    elif family == "workspace_lineage":
        passed, detail = check_workspace_lineage_variant(workspace, oracle)
    elif family == "tool_recovery":
        passed, detail = _check_tool_recovery(
            workspace,
            oracle,
            run_dir=run_dir,
            task_id=task_id,
        )
        failure_kind = None if passed else diagnose_tool_recovery_failure(
            oracle,
            run_dir=run_dir,
            task_id=task_id,
        )
        return VariantGrade.binary(passed, detail, failure_kind=failure_kind)
    elif family in {"stateful_world", "dependency_world"}:
        passed, detail = _check_mediated_world(
            family,
            workspace,
            oracle,
            run_dir=run_dir,
            task_id=task_id,
        )
    else:
        return VariantGrade.binary(False, f"unknown parametric family: {family}")
    return VariantGrade.binary(passed, detail)


def check_variant(
    family: str,
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None = None,
    task_id: str | None = None,
) -> tuple[bool, str]:
    grade = evaluate_variant(
        family,
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=task_id,
    )
    return grade.passed, grade.detail


def diagnose_variant_failure(
    family: str,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None = None,
    task_id: str | None = None,
) -> str | None:
    if family == "tool_recovery":
        return diagnose_tool_recovery_failure(
            oracle,
            run_dir=run_dir,
            task_id=task_id,
        )
    return None


__all__ = [
    "ConfigTraversalPressure",
    "CrossArtifactPressure",
    "DependencyWorldPressure",
    "EpistemicTwinPressure",
    "ExpensePressure",
    "StatefulWorldPressure",
    "ToolRecoveryPressure",
    "WideRetrievalPressure",
    "WorkspaceLineagePressure",
    "FAMILIES",
    "VariantGrade",
    "check_variant",
    "diagnose_variant_failure",
    "evaluate_variant",
    "materialize_variant",
    "normalize_parameters",
    "start_variant_runtime",
]
