from __future__ import annotations

from pathlib import Path

from aios_bench.frontier_runner import semantic_source_paths
from aios_bench.horizon import (
    DEFAULT_HORIZON_PROFILE,
    HORIZON_CONTEXT_KIND,
    get_horizon_profile,
)
from aios_bench.parametric import FAMILIES
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"


def test_default_horizon_profile_is_explicit_and_complete() -> None:
    profile = get_horizon_profile()

    assert profile.id == DEFAULT_HORIZON_PROFILE
    assert len(profile.cells) == 15
    assert len({cell.id for cell in profile.cells}) == 15
    assert len(profile.digest) == 64
    assert {
        cell.family for cell in profile.cells
    } == {
        "stateful_world",
        "dependency_world",
        "workspace_lineage",
        "tool_recovery",
        "wide_retrieval",
    }
    for family in {
        "stateful_world",
        "dependency_world",
        "workspace_lineage",
        "tool_recovery",
        "wide_retrieval",
    }:
        cells = profile.family_cells(family)
        assert [cell.path_index for cell in cells] == [1, 2, 3]


def test_horizon_profile_reuses_existing_frontier_v4_tasks() -> None:
    profile = get_horizon_profile()
    task_ids = {task.id for task in load_tasks(TASK_ROOT, "frontier_v4")}

    assert {cell.task_id for cell in profile.cells} <= task_ids


def test_horizon_cell_parameters_preserve_complete_v4_identity() -> None:
    profile = get_horizon_profile()
    cell = profile.cells[0]

    parameters = profile.parameters_for(cell)

    assert set(parameters) == FAMILIES
    assert parameters[cell.family] == dict(cell.parameters)
    assert parameters["epistemic_twins"]["pair_count"] == 6
    assert parameters["cross_artifact"]["row_count"] == 72


def test_horizon_context_carries_profile_and_exact_cell_identity() -> None:
    profile = get_horizon_profile()
    cell = profile.family_cells("tool_recovery")[1]

    context = profile.context_for(cell)

    assert context["kind"] == HORIZON_CONTEXT_KIND
    assert context["profile_id"] == profile.id
    assert context["profile_digest"] == profile.digest
    assert context["cell_id"] == cell.id
    assert context["path_index"] == 2
    assert context["parameters"] == dict(cell.parameters)
    assert context["family_cell_ids"] == [
        item.id for item in profile.family_cells("tool_recovery")
    ]
    assert context["axis_roles"]["transient_failures"] == "recovery_event_count"
    assert "not an assumed monotonic difficulty scale" in context["interpretation"]


def test_horizon_profile_and_analysis_do_not_change_suite_semantics() -> None:
    names = {path.name for path in semantic_source_paths(ROOT)}

    assert "horizon.py" not in names
    assert "horizon_analysis.py" not in names
    assert "horizon_execution.py" not in names
