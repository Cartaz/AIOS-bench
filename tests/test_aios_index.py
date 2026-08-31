from pathlib import Path

import pytest

from core.benchmark.aios_index import (
    AIOS_INDEX_CONTEXT_KIND,
    DEFAULT_AIOS_INDEX_PROFILE,
    AIOSIndexProfile,
    IndexEntry,
    get_aios_index_profile,
)
from core.benchmark.parametric import normalize_parameters
from core.benchmark.paths import TASKS_ROOT
from core.benchmark.tasks import load_tasks


EXPECTED_TASK_IDS = {
    "support_dependency_001",
    "data_cross_artifact_001",
    "reasoning_epistemic_001",
    "retrieval_wide_001",
    "software_black_box_001",
    "tool_use_lineage_001",
    "tool_recovery_001",
}
EXPECTED_FAMILIES = {
    "dependency_world",
    "workspace_lineage",
    "tool_recovery",
    "wide_retrieval",
    "cross_artifact",
    "epistemic_twins",
    "black_box_reconstruction",
}


def test_default_aios_index_is_compact_canonical_v4_selection() -> None:
    profile = get_aios_index_profile()
    tasks = load_tasks(TASKS_ROOT, "frontier_v4")
    selected = profile.select_tasks(tasks)

    assert profile.id == DEFAULT_AIOS_INDEX_PROFILE
    assert len(selected) == 7
    assert {task.id for task in selected} == EXPECTED_TASK_IDS
    assert len(selected) < len(tasks)
    assert all(task.tier == 5 for task in selected)


def test_aios_index_profile_digest_covers_selection_and_only_selected_pressures() -> None:
    profile = get_aios_index_profile()
    canonical = normalize_parameters()

    assert set(profile.parameters()) == EXPECTED_FAMILIES
    assert profile.parameters() == {
        family: canonical[family]
        for family in profile.pressure_families
    }
    assert len(profile.digest) == 64
    assert profile.comparison_id == f"{profile.id}@{profile.digest}"

    changed = AIOSIndexProfile(
        "changed",
        profile.entries[:-1],
    )
    assert changed.digest != profile.digest


def test_aios_index_context_is_self_describing_without_cloning_task_definitions() -> None:
    profile = get_aios_index_profile()
    context = profile.context()

    assert context["kind"] == AIOS_INDEX_CONTEXT_KIND
    assert context["profile_name"] == profile.id
    assert context["profile_id"] == profile.comparison_id
    assert context["profile_digest"] == profile.digest
    assert context["task_count"] == len(profile.entries)
    assert set(context["task_ids"]) == EXPECTED_TASK_IDS
    assert set(context["roles"]) == EXPECTED_TASK_IDS
    assert set(context["pressure_coordinates"]) == EXPECTED_FAMILIES


def test_aios_index_rejects_missing_catalog_task() -> None:
    profile = AIOSIndexProfile("broken", (IndexEntry("missing_task", "test"),))
    with pytest.raises(ValueError, match="missing tasks"):
        profile.select_tasks([])


def test_aios_index_rejects_dependency_outside_profile() -> None:
    from core.benchmark.models import Task

    task = Task(
        id="dependent_task",
        category="autonomy",
        prompt="x",
        depends_on=("required_task",),
        acceptance=({"type": "reference", "task_id": "dependent_task"},),
    )
    profile = AIOSIndexProfile("broken", (IndexEntry("dependent_task", "test"),))
    with pytest.raises(ValueError, match="outside the profile"):
        profile.select_tasks([task])


def test_aios_index_rejects_family_drift() -> None:
    tasks = load_tasks(TASKS_ROOT, "frontier_v4")
    profile = AIOSIndexProfile(
        "broken",
        (IndexEntry("tool_recovery_001", "test", "wide_retrieval"),),
    )

    with pytest.raises(ValueError, match="family drift"):
        profile.select_tasks(tasks)


def test_aios_index_module_has_no_catalog_copy() -> None:
    # The profile is metadata only. Canonical task prompts/checks stay in the
    # ordinary Frontier v4 JSON catalog.
    source = Path(__file__).parents[1] / "core" / "benchmark" / "aios_index.py"
    text = source.read_text(encoding="utf-8")
    assert "parametric_reference" not in text
    assert "acceptance" not in text
