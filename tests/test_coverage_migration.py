from __future__ import annotations

import json
from pathlib import Path

from core.benchmark.evaluators import evaluate_artifacts
from core.benchmark.parametric.coverage_migration import (
    CoverageMigrationPressure,
    evaluate_coverage_migration_variant,
    generate_coverage_migration_variant,
)
from core.benchmark.parametric_goldens import materialize_parametric_golden


def _materialize(tmp_path: Path, *, seed: int = 101):
    workspace = tmp_path / "workspace"
    oracle = generate_coverage_migration_variant(
        workspace,
        seed=seed,
        pressure=CoverageMigrationPressure(targets=6, current_active=2, historical_decoys=3),
    )
    return workspace, oracle


def test_coverage_migration_exact_solution_passes_with_full_metrics(tmp_path: Path) -> None:
    workspace, oracle = _materialize(tmp_path)
    materialize_parametric_golden("coverage_migration", workspace, oracle)

    result = evaluate_coverage_migration_variant(workspace, oracle)

    assert result["passed"] is True
    assert result["metrics"] == {
        "schema": "aios-bench/coverage/v1",
        "true_positives": 6,
        "false_positives": 0,
        "false_negatives": 0,
        "precision": 1.0,
        "recall": 1.0,
        "completion": 1.0,
        "required_count": 6,
    }


def test_partial_migration_fails_but_preserves_continuous_coverage(tmp_path: Path) -> None:
    workspace, oracle = _materialize(tmp_path)
    targets = list(oracle["targets"])
    expected = oracle["expected_targets"]
    for relative in targets[:3]:
        path = workspace / relative
        path.write_text(json.dumps(expected[relative], indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = evaluate_coverage_migration_variant(workspace, oracle)

    assert result["passed"] is False
    assert result["metrics"]["true_positives"] == 3
    assert result["metrics"]["false_negatives"] == 3
    assert result["metrics"]["false_positives"] == 0
    assert result["metrics"]["precision"] == 1.0
    assert result["metrics"]["recall"] == 0.5
    assert result["metrics"]["completion"] == 0.5


def test_out_of_scope_edit_is_false_positive_and_prevents_pass(tmp_path: Path) -> None:
    workspace, oracle = _materialize(tmp_path)
    materialize_parametric_golden("coverage_migration", workspace, oracle)
    protected = next(
        relative
        for relative in oracle["protected_sha256"]
        if str(relative).startswith("config/history/")
    )
    path = workspace / str(protected)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["request_timeout_ms"] = data.pop("timeout_ms")
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = evaluate_coverage_migration_variant(workspace, oracle)

    assert result["passed"] is False
    assert result["metrics"]["true_positives"] == 6
    assert result["metrics"]["false_negatives"] == 0
    assert result["metrics"]["false_positives"] == 1
    assert result["metrics"]["recall"] == 1.0
    assert result["metrics"]["precision"] == 6 / 7
    assert result["metrics"]["completion"] == 6 / 7


def test_parametric_reference_persists_coverage_metrics_without_changing_acceptance_score(tmp_path: Path) -> None:
    workspace, oracle = _materialize(tmp_path)
    run_dir = tmp_path / "run"
    oracle_dir = run_dir / "oracles"
    oracle_dir.mkdir(parents=True)
    task_id = "tool_use_coverage_001"
    (oracle_dir / f"{task_id}.json").write_text(
        json.dumps(oracle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    expected = oracle["expected_targets"]
    for relative in list(oracle["targets"])[:2]:
        path = workspace / relative
        path.write_text(json.dumps(expected[relative], indent=2, sort_keys=True) + "\n", encoding="utf-8")

    evaluation = evaluate_artifacts(
        workspace,
        [{
            "type": "parametric_reference",
            "family": "coverage_migration",
            "task_id": task_id,
            "weight": 10,
            "fatal": True,
        }],
        run_dir=run_dir,
    )

    assert evaluation["passed"] is False
    assert evaluation["acceptance_score"] == 0.0
    metrics = evaluation["results"][0]["metrics"]
    assert metrics["true_positives"] == 2
    assert metrics["false_negatives"] == 4
    assert metrics["completion"] == 1 / 3
