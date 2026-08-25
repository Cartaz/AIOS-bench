from __future__ import annotations

import json
from pathlib import Path

from aios_bench.experiments import derive_seed
from aios_bench.frontier_v4_runner import FrontierV4Runner, SEMANTIC_DIRS, SEMANTIC_FILES
from aios_bench.runner import AGENTS
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"


def _runner(
    results: Path,
    seed: int,
    run_id: str,
    parameters: dict | None = None,
    max_output_tokens: int = 65536,
) -> FrontierV4Runner:
    return FrontierV4Runner(
        ROOT,
        AGENTS["piagent"],
        results,
        task_timeout=1,
        total_timeout=None,
        model="test",
        run_id=run_id,
        variant_base_seed=seed,
        parametric_parameters=parameters,
        max_output_tokens=max_output_tokens,
    )


def test_frontier_v4_is_separate_from_frozen_v3_catalog() -> None:
    v3 = load_tasks(TASK_ROOT)
    v4 = load_tasks(TASK_ROOT, "frontier_v4")

    assert len(v3) == 28
    assert [task.id for task in v4] == ["autonomy_expense_001", "tool_use_config_001"]
    assert all(task.revision == 4 for task in v4)
    assert all(any(check["type"] == "parametric_reference" for check in task.acceptance) for task in v4)


def test_frontier_v4_uses_scheduler_compatible_task_seed(tmp_path: Path) -> None:
    task = load_tasks(TASK_ROOT, "frontier_v4")[0]
    runner = _runner(tmp_path / "results", 123, "seed-check")

    assert runner._task_seed(task) == derive_seed(123, "task", task.id)


def test_same_v4_seed_materializes_identical_variant_across_runners(tmp_path: Path) -> None:
    task = load_tasks(TASK_ROOT, "frontier_v4")[0]
    first = _runner(tmp_path / "a", 42, "first")
    second = _runner(tmp_path / "b", 42, "second")

    workspace_a = first._workspace(task)
    workspace_b = second._workspace(task)
    oracle_a = json.loads((first.run_dir / "oracles" / f"{task.id}.json").read_text(encoding="utf-8"))
    oracle_b = json.loads((second.run_dir / "oracles" / f"{task.id}.json").read_text(encoding="utf-8"))

    assert oracle_a["variant_digest"] == oracle_b["variant_digest"]
    assert oracle_a["seed"] == oracle_b["seed"] == derive_seed(42, "task", task.id)
    assert (workspace_a / "data" / "transactions.csv").read_bytes() == (
        workspace_b / "data" / "transactions.csv"
    ).read_bytes()
    assert not (workspace_a / "oracles").exists()
    assert not (workspace_b / "oracles").exists()


def test_different_v4_repeat_seed_changes_variant(tmp_path: Path) -> None:
    task = load_tasks(TASK_ROOT, "frontier_v4")[0]
    first = _runner(tmp_path / "a", 42, "first")
    second = _runner(tmp_path / "b", 43, "second")

    first._workspace(task)
    second._workspace(task)
    identity_a = first._result_identity(task)
    identity_b = second._result_identity(task)

    assert identity_a["variant_seed"] != identity_b["variant_seed"]
    assert identity_a["variant_digest"] != identity_b["variant_digest"]
    assert identity_a["variant_parameters"] == {
        "rows": 48,
        "malformed_rows": 2,
        "distractor_files": 3,
        "months": 6,
    }


def test_landscape_profile_excludes_only_pressure_coordinates(tmp_path: Path) -> None:
    first = _runner(
        tmp_path / "a",
        42,
        "first",
        {"expense_report": {"rows": 48, "malformed_rows": 2, "distractor_files": 3, "months": 6}},
    )
    second = _runner(
        tmp_path / "b",
        42,
        "second",
        {"expense_report": {"rows": 96, "malformed_rows": 4, "distractor_files": 8, "months": 9}},
    )
    changed_guard = _runner(
        tmp_path / "c",
        42,
        "changed-guard",
        {"expense_report": {"rows": 96, "malformed_rows": 4, "distractor_files": 8, "months": 9}},
        max_output_tokens=32768,
    )

    assert first.execution_fingerprint != second.execution_fingerprint
    assert first.landscape_execution_fingerprint == second.landscape_execution_fingerprint
    assert changed_guard.landscape_execution_fingerprint != second.landscape_execution_fingerprint

    task = load_tasks(TASK_ROOT, "frontier_v4")[0]
    assert first._result_identity(task)["landscape_execution_fingerprint"] == (
        first.landscape_execution_fingerprint
    )


def test_frontier_v4_semantic_fingerprint_covers_generators() -> None:
    assert "frontier_v4_runner.py" in SEMANTIC_FILES
    assert "parametric" in SEMANTIC_DIRS
