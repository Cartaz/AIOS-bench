from __future__ import annotations

import copy
import json
from pathlib import Path

from aios_bench.evaluators import evaluate_artifacts
from aios_bench.failures import CROSS_ARTIFACT_MISMATCH, classify_failure
from aios_bench.parametric import CrossArtifactPressure, materialize_variant
from aios_bench.parametric.cross_artifact import grade_cross_artifact_variant
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"


def _write_artifacts(
    workspace: Path,
    expected: dict,
    *,
    machine: dict | None = None,
    human: dict | None = None,
) -> None:
    machine_value = copy.deepcopy(expected if machine is None else machine)
    human_value = copy.deepcopy(expected if human is None else human)
    reports = workspace / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "account_summary.json").write_text(
        json.dumps(machine_value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Account summary",
        "",
        f"source: {human_value['source']}",
        "",
        "| account | posted_count | net_cents |",
        "| --- | ---: | ---: |",
    ]
    for row in human_value["groups"]:
        lines.append(f"| {row['account']} | {row['posted_count']} | {row['net_cents']} |")
    lines.extend([
        "",
        f"posted_count: {human_value['posted_count']}",
        f"grand_total_cents: {human_value['grand_total_cents']}",
        "",
    ])
    (reports / "account_summary.md").write_text("\n".join(lines), encoding="utf-8")


def _task():
    return next(
        task
        for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "data_cross_artifact_001"
    )


def _write_oracle(run_dir: Path, task_id: str, oracle: dict) -> None:
    path = run_dir / "oracles" / f"{task_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(oracle, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_cross_artifact_variant_is_deterministic_and_pressure_sensitive(tmp_path: Path) -> None:
    pressure = CrossArtifactPressure(
        row_count=96,
        group_count=8,
        excluded_rows=16,
        adjustment_rows=12,
        distractor_files=5,
    )
    first = materialize_variant(
        "cross_artifact", tmp_path / "first", seed=2026, parameters=pressure.to_dict()
    )
    second = materialize_variant(
        "cross_artifact", tmp_path / "second", seed=2026, parameters=pressure.to_dict()
    )
    other_seed = materialize_variant(
        "cross_artifact", tmp_path / "seed", seed=2027, parameters=pressure.to_dict()
    )
    other_pressure = materialize_variant(
        "cross_artifact",
        tmp_path / "pressure",
        seed=2026,
        parameters={
            "row_count": 120,
            "group_count": 9,
            "excluded_rows": 20,
            "adjustment_rows": 14,
            "distractor_files": 6,
        },
    )

    assert first["variant_digest"] == second["variant_digest"]
    assert first["expected"] == second["expected"]
    assert first["variant_digest"] != other_seed["variant_digest"]
    assert first["variant_digest"] != other_pressure["variant_digest"]


def test_cross_artifact_golden_requires_both_correct_reconciled_outputs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("cross_artifact", workspace, seed=42)
    _write_artifacts(workspace, oracle["expected"])

    grade = grade_cross_artifact_variant(workspace, oracle)

    assert grade.passed is True
    assert grade.score == 1.0
    assert grade.metrics["machine_accuracy"] == 1.0
    assert grade.metrics["human_accuracy"] == 1.0
    assert grade.metrics["reconciliation_rate"] == 1.0
    assert grade.metrics["strict_complete_pass"] is True


def test_cross_artifact_detects_json_markdown_mismatch(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("cross_artifact", workspace, seed=43)
    human = copy.deepcopy(oracle["expected"])
    human["groups"][0]["net_cents"] += 1
    _write_artifacts(workspace, oracle["expected"], human=human)

    grade = grade_cross_artifact_variant(workspace, oracle)

    assert grade.passed is False
    assert grade.failure_kind == CROSS_ARTIFACT_MISMATCH
    assert grade.metrics["machine_accuracy"] == 1.0
    assert grade.metrics["human_accuracy"] < 1.0
    assert grade.metrics["reconciliation_rate"] < 1.0
    assert 0.0 < grade.score < 1.0


def test_cross_artifact_consistently_wrong_outputs_do_not_report_mismatch(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("cross_artifact", workspace, seed=44)
    wrong = copy.deepcopy(oracle["expected"])
    wrong["grand_total_cents"] += 123
    _write_artifacts(workspace, oracle["expected"], machine=wrong, human=wrong)

    grade = grade_cross_artifact_variant(workspace, oracle)

    assert grade.passed is False
    assert grade.failure_kind is None
    assert grade.metrics["reconciliation_rate"] == 1.0
    assert grade.metrics["machine_accuracy"] < 1.0
    assert grade.metrics["human_accuracy"] < 1.0


def test_cross_artifact_rejects_unsupported_group_even_when_both_artifacts_agree(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("cross_artifact", workspace, seed=45)
    wrong = copy.deepcopy(oracle["expected"])
    wrong["groups"].append({
        "account": "acct-unsupported",
        "posted_count": 1,
        "net_cents": 999,
    })
    _write_artifacts(workspace, oracle["expected"], machine=wrong, human=wrong)

    grade = grade_cross_artifact_variant(workspace, oracle)

    assert grade.passed is False
    assert grade.failure_kind is None
    assert grade.metrics["reconciliation_rate"] == 1.0
    assert grade.metrics["machine_extra_groups"] == 1
    assert grade.metrics["human_extra_groups"] == 1


def test_cross_artifact_source_tamper_invalidates_before_artifact_scoring(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("cross_artifact", workspace, seed=46)
    _write_artifacts(workspace, oracle["expected"])
    ledger = workspace / "source" / "current" / "ledger.csv"
    ledger.write_text(ledger.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")

    grade = grade_cross_artifact_variant(workspace, oracle)

    assert grade.passed is False
    assert grade.score == 0.0
    assert "protected source modified" in grade.detail


def test_cross_artifact_evaluator_preserves_partial_metrics_and_failure_kind(tmp_path: Path) -> None:
    task = _task()
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("cross_artifact", workspace, seed=47)
    _write_oracle(run_dir, task.id, oracle)
    human = copy.deepcopy(oracle["expected"])
    human["posted_count"] -= 1
    _write_artifacts(workspace, oracle["expected"], human=human)

    evaluation = evaluate_artifacts(
        workspace,
        list(task.acceptance),
        run_dir=run_dir,
        fixture_root=ROOT / "benchmarks" / "fixtures" / "workspace",
    )
    events = [{"type": "deterministic_evaluation", "result": evaluation}]

    assert evaluation["passed"] is False
    assert evaluation["failure_kind"] == CROSS_ARTIFACT_MISMATCH
    metrics = evaluation["metrics"]["cross_artifact"]
    assert metrics["reconciliation_rate"] < 1.0
    assert classify_failure(
        status="failed",
        success=False,
        execution_success=True,
        evaluation_passed=False,
        events=events,
    ) == CROSS_ARTIFACT_MISMATCH
