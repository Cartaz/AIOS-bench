from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from ..black_box_api import start_black_box_runtime, write_black_box_client
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
from .black_box_reconstruction import (
    BlackBoxReconstructionPressure,
    generate_black_box_reconstruction_variant,
    grade_black_box_reconstruction_variant,
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
from .learning_transfer import (
    LearningTransferPressure,
    generate_learning_transfer_variant,
    grade_learning_transfer_variant,
)
from .persistent_memory import (
    PersistentMemoryPressure,
    generate_persistent_memory_variant,
    grade_persistent_memory_variant,
)
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


Generator = Callable[..., dict[str, Any]]
PostMaterializer = Callable[[Path, dict[str, Any]], dict[str, Any]]
RuntimeStarter = Callable[[Path, Path, str, Mapping[str, Any]], TaskRuntime]
Grader = Callable[
    [Path, Mapping[str, Any], Path | None, str | None],
    VariantGrade,
]
FailureDiagnoser = Callable[[Mapping[str, Any], Path | None, str | None], str | None]


@dataclass(frozen=True)
class ParametricFamilySpec:
    """One declarative generated-family integration contract.

    Pressure validation, generation, optional workspace/runtime adaptation,
    deterministic grading, and optional benchmark-owned persistent state are
    registered once. Public dispatch functions below remain stable while
    family-specific complexity stays behind these callables.
    """

    pressure_type: Any
    generator: Generator
    grader: Grader
    post_materialize: PostMaterializer | None = None
    runtime: RuntimeStarter | None = None
    diagnose: FailureDiagnoser | None = None
    uses_context: bool = False
    persistent_paths: tuple[str, ...] = ()


def _reseal_variant(oracle: dict[str, Any]) -> dict[str, Any]:
    core = {key: value for key, value in oracle.items() if key != "variant_digest"}
    payload = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    oracle["variant_digest"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return oracle


def _post_black_box(workspace: Path, oracle: dict[str, Any]) -> dict[str, Any]:
    write_black_box_client(workspace)
    return _reseal_variant(oracle)


def _post_tool_recovery(workspace: Path, oracle: dict[str, Any]) -> dict[str, Any]:
    write_tool_recovery_client(workspace)
    return _reseal_variant(oracle)


def _post_stateful_world(workspace: Path, oracle: dict[str, Any]) -> dict[str, Any]:
    write_world_api_client(workspace)
    oracle["mutation_interface"] = SupportWorldService.contract()
    return _reseal_variant(oracle)


def _post_dependency_world(workspace: Path, oracle: dict[str, Any]) -> dict[str, Any]:
    write_world_api_client(workspace)
    oracle["mutation_interface"] = SupportDependencyWorldService.contract()
    return _reseal_variant(oracle)


def _grade_expense(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    passed, detail = check_expense_variant(workspace, oracle)
    return VariantGrade.binary(passed, detail)


def _grade_config(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    passed, detail = check_config_traversal_variant(workspace, oracle)
    return VariantGrade.binary(passed, detail)


def _grade_lineage(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    passed, detail = check_workspace_lineage_variant(workspace, oracle)
    return VariantGrade.binary(passed, detail)


def _grade_wide_retrieval(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    return grade_wide_retrieval_variant(workspace, oracle)


def _grade_cross_artifact(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    return grade_cross_artifact_variant(workspace, oracle)


def _grade_epistemic_twins(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    return grade_epistemic_twins_variant(workspace, oracle)


def _grade_black_box(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    return grade_black_box_reconstruction_variant(
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=task_id,
    )


def _grade_persistent_memory(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    return grade_persistent_memory_variant(workspace, oracle)


def _grade_learning_transfer(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    return grade_learning_transfer_variant(workspace, oracle)


def _check_mediated_world(
    checker: Callable[[Path, Mapping[str, Any]], tuple[bool, str]],
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None,
    task_id: str | None,
) -> tuple[bool, str]:
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


def _grade_stateful_world(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    passed, detail = _check_mediated_world(
        check_stateful_world_variant,
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=task_id,
    )
    return VariantGrade.binary(passed, detail)


def _grade_dependency_world(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    passed, detail = _check_mediated_world(
        check_dependency_world_variant,
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=task_id,
    )
    return VariantGrade.binary(passed, detail)


def _grade_tool_recovery(
    workspace: Path,
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> VariantGrade:
    passed, detail = check_tool_recovery_variant(workspace, oracle)
    if passed:
        provenance_ok, provenance_detail = verify_tool_recovery_log(
            oracle,
            run_dir=run_dir,
            task_id=task_id,
        )
        if provenance_ok:
            return VariantGrade.binary(True, f"{detail}; {provenance_detail}")
        detail = provenance_detail
    failure_kind = diagnose_tool_recovery_failure(
        oracle,
        run_dir=run_dir,
        task_id=task_id,
    )
    return VariantGrade.binary(False, detail, failure_kind=failure_kind)


def _diagnose_tool_recovery(
    oracle: Mapping[str, Any],
    run_dir: Path | None,
    task_id: str | None,
) -> str | None:
    return diagnose_tool_recovery_failure(
        oracle,
        run_dir=run_dir,
        task_id=task_id,
    )


FAMILY_SPECS: dict[str, ParametricFamilySpec] = {
    "expense_report": ParametricFamilySpec(
        ExpensePressure,
        generate_expense_variant,
        _grade_expense,
    ),
    "config_traversal": ParametricFamilySpec(
        ConfigTraversalPressure,
        generate_config_traversal_variant,
        _grade_config,
    ),
    "stateful_world": ParametricFamilySpec(
        StatefulWorldPressure,
        generate_stateful_world_variant,
        _grade_stateful_world,
        post_materialize=_post_stateful_world,
        runtime=start_support_world_runtime,
    ),
    "dependency_world": ParametricFamilySpec(
        DependencyWorldPressure,
        generate_dependency_world_variant,
        _grade_dependency_world,
        post_materialize=_post_dependency_world,
        runtime=start_dependency_world_runtime,
    ),
    "workspace_lineage": ParametricFamilySpec(
        WorkspaceLineagePressure,
        generate_workspace_lineage_variant,
        _grade_lineage,
    ),
    "tool_recovery": ParametricFamilySpec(
        ToolRecoveryPressure,
        generate_tool_recovery_variant,
        _grade_tool_recovery,
        post_materialize=_post_tool_recovery,
        runtime=start_tool_recovery_runtime,
        diagnose=_diagnose_tool_recovery,
    ),
    "wide_retrieval": ParametricFamilySpec(
        WideRetrievalPressure,
        generate_wide_retrieval_variant,
        _grade_wide_retrieval,
    ),
    "cross_artifact": ParametricFamilySpec(
        CrossArtifactPressure,
        generate_cross_artifact_variant,
        _grade_cross_artifact,
    ),
    "epistemic_twins": ParametricFamilySpec(
        EpistemicTwinPressure,
        generate_epistemic_twins_variant,
        _grade_epistemic_twins,
    ),
    "black_box_reconstruction": ParametricFamilySpec(
        BlackBoxReconstructionPressure,
        generate_black_box_reconstruction_variant,
        _grade_black_box,
        post_materialize=_post_black_box,
        runtime=start_black_box_runtime,
    ),
    "persistent_memory": ParametricFamilySpec(
        PersistentMemoryPressure,
        generate_persistent_memory_variant,
        _grade_persistent_memory,
        uses_context=True,
        persistent_paths=(".agent_memory",),
    ),
    "learning_transfer": ParametricFamilySpec(
        LearningTransferPressure,
        generate_learning_transfer_variant,
        _grade_learning_transfer,
        uses_context=True,
        persistent_paths=("skills",),
    ),
}

FAMILIES = set(FAMILY_SPECS)


def _family_spec(family: str) -> ParametricFamilySpec:
    try:
        return FAMILY_SPECS[family]
    except KeyError as exc:
        raise ValueError(f"unknown parametric family: {family}") from exc


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
        family: spec.pressure_type.from_mapping(supplied.get(family, {})).to_dict()
        for family, spec in FAMILY_SPECS.items()
    }


def materialize_variant(
    family: str,
    workspace: Path,
    *,
    seed: int,
    parameters: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    spec = _family_spec(family)
    pressure = spec.pressure_type.from_mapping(parameters or {})
    if spec.uses_context:
        oracle = spec.generator(
            workspace,
            seed=int(seed),
            pressure=pressure,
            context=dict(context or {}),
        )
    else:
        oracle = spec.generator(workspace, seed=int(seed), pressure=pressure)
    if spec.post_materialize is not None:
        oracle = spec.post_materialize(workspace, oracle)
    return oracle


def persistent_state_paths(family: str) -> tuple[str, ...]:
    """Return benchmark-owned state paths persisted between related warm tasks."""
    return _family_spec(family).persistent_paths


def start_variant_runtime(
    family: str,
    workspace: Path,
    *,
    run_dir: Path,
    task_id: str,
    oracle: Mapping[str, Any],
) -> TaskRuntime:
    spec = FAMILY_SPECS.get(family)
    if spec is None or spec.runtime is None:
        return TaskRuntime()
    return spec.runtime(workspace, run_dir, task_id, oracle)


def evaluate_variant(
    family: str,
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None = None,
    task_id: str | None = None,
) -> VariantGrade:
    """Grade one generated family through a common structured contract."""
    spec = FAMILY_SPECS.get(family)
    if spec is None:
        return VariantGrade.binary(False, f"unknown parametric family: {family}")
    return spec.grader(workspace, oracle, run_dir, task_id)


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
    spec = FAMILY_SPECS.get(family)
    if spec is None or spec.diagnose is None:
        return None
    return spec.diagnose(oracle, run_dir, task_id)


__all__ = [
    "BlackBoxReconstructionPressure",
    "ConfigTraversalPressure",
    "CrossArtifactPressure",
    "DependencyWorldPressure",
    "EpistemicTwinPressure",
    "ExpensePressure",
    "FAMILIES",
    "FAMILY_SPECS",
    "LearningTransferPressure",
    "ParametricFamilySpec",
    "PersistentMemoryPressure",
    "StatefulWorldPressure",
    "ToolRecoveryPressure",
    "VariantGrade",
    "WideRetrievalPressure",
    "WorkspaceLineagePressure",
    "check_variant",
    "diagnose_variant_failure",
    "evaluate_variant",
    "materialize_variant",
    "normalize_parameters",
    "persistent_state_paths",
    "start_variant_runtime",
]