from __future__ import annotations

import copy
import json
from pathlib import Path

from aios_bench.evaluators import evaluate_artifacts
from aios_bench.parametric import WideRetrievalPressure, materialize_variant
from aios_bench.parametric.wide_retrieval import grade_wide_retrieval_variant
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"


def _write_report(workspace: Path, oracle: dict, rows: list[dict] | None = None) -> None:
    report = workspace / "reports" / "wide_retrieval.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(
            {
                "query_id": oracle["query_id"],
                "records": copy.deepcopy(oracle["target_rows"] if rows is None else rows),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_oracle(run_dir: Path, task_id: str, oracle: dict) -> None:
    path = run_dir / "oracles" / f"{task_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(oracle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _task():
    return next(
        task
        for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "retrieval_wide_001"
    )


def test_wide_retrieval_variant_is_deterministic_and_pressure_sensitive(tmp_path: Path) -> None:
    pressure = WideRetrievalPressure(
        corpus_size=120,
        target_count=16,
        duplicate_records=18,
        conflict_records=14,
        source_depth=4,
    )
    first = materialize_variant(
        "wide_retrieval",
        tmp_path / "first",
        seed=2026,
        parameters=pressure.to_dict(),
    )
    second = materialize_variant(
        "wide_retrieval",
        tmp_path / "second",
        seed=2026,
        parameters=pressure.to_dict(),
    )
    other_seed = materialize_variant(
        "wide_retrieval",
        tmp_path / "other-seed",
        seed=2027,
        parameters=pressure.to_dict(),
    )
    other_pressure = materialize_variant(
        "wide_retrieval",
        tmp_path / "other-pressure",
        seed=2026,
        parameters={
            "corpus_size": 144,
            "target_count": 18,
            "duplicate_records": 20,
            "conflict_records": 16,
            "source_depth": 5,
        },
    )

    assert first["variant_digest"] == second["variant_digest"]
    assert first["target_rows"] == second["target_rows"]
    assert first["variant_digest"] != other_seed["variant_digest"]
    assert first["variant_digest"] != other_pressure["variant_digest"]


def test_wide_retrieval_golden_is_strict_complete_pass(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("wide_retrieval", workspace, seed=42)
    _write_report(workspace, oracle)

    grade = grade_wide_retrieval_variant(workspace, oracle)

    assert grade.passed is True
    assert grade.score == 1.0
    assert grade.failure_kind is None
    assert grade.metrics["strict_complete_pass"] is True
    assert grade.metrics["record_precision"] == 1.0
    assert grade.metrics["record_recall"] == 1.0
    assert grade.metrics["record_f1"] == 1.0
    assert grade.metrics["field_accuracy"] == 1.0
    assert grade.metrics["provenance_recall"] == 1.0


def test_wide_retrieval_missing_record_reports_incomplete_retrieval(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("wide_retrieval", workspace, seed=43)
    rows = copy.deepcopy(oracle["target_rows"][:-1])
    _write_report(workspace, oracle, rows)

    grade = grade_wide_retrieval_variant(workspace, oracle)

    assert grade.passed is False
    assert grade.metrics["record_precision"] == 1.0
    assert grade.metrics["record_recall"] < 1.0
    assert grade.metrics["missing_record_count"] == 1
    assert grade.failure_kind == "INCOMPLETE_RETRIEVAL"
    assert 0.0 < grade.score < 1.0


def test_wide_retrieval_extra_record_lowers_precision(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("wide_retrieval", workspace, seed=44)
    rows = copy.deepcopy(oracle["target_rows"])
    extra = copy.deepcopy(rows[0])
    extra["record_id"] = "REC-99999"
    rows.append(extra)
    _write_report(workspace, oracle, rows)

    grade = grade_wide_retrieval_variant(workspace, oracle)

    assert grade.passed is False
    assert grade.metrics["record_recall"] == 1.0
    assert grade.metrics["record_precision"] < 1.0
    assert grade.metrics["extra_record_count"] == 1


def test_wide_retrieval_field_error_is_measured_separately(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("wide_retrieval", workspace, seed=45)
    rows = copy.deepcopy(oracle["target_rows"])
    rows[0]["owner"] = "invented-owner"
    _write_report(workspace, oracle, rows)

    grade = grade_wide_retrieval_variant(workspace, oracle)

    assert grade.passed is False
    assert grade.metrics["record_f1"] == 1.0
    assert grade.metrics["field_accuracy"] < 1.0
    assert grade.metrics["provenance_recall"] == 1.0


def test_wide_retrieval_stale_citation_is_wrong_authority(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("wide_retrieval", workspace, seed=46)
    rows = copy.deepcopy(oracle["target_rows"])
    rows[0]["citation"] = {
        "path": "corpus/archive/2025-retired/records.jsonl",
        "line": 1,
    }
    _write_report(workspace, oracle, rows)

    grade = grade_wide_retrieval_variant(workspace, oracle)

    assert grade.passed is False
    assert grade.metrics["record_f1"] == 1.0
    assert grade.metrics["field_accuracy"] == 1.0
    assert grade.metrics["provenance_recall"] < 1.0
    assert grade.metrics["wrong_authority_count"] == 1
    assert grade.metrics["stale_source_count"] == 1
    assert grade.failure_kind == "WRONG_AUTHORITY"


def test_wide_retrieval_source_tamper_invalidates_grade(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("wide_retrieval", workspace, seed=47)
    _write_report(workspace, oracle)
    authority = workspace / "corpus" / "AUTHORITY.json"
    authority.write_text(authority.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")

    grade = grade_wide_retrieval_variant(workspace, oracle)

    assert grade.passed is False
    assert grade.score == 0.0
    assert "protected source modified" in grade.detail


def test_parametric_evaluator_preserves_partial_retrieval_credit_and_metrics(tmp_path: Path) -> None:
    task = _task()
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("wide_retrieval", workspace, seed=48)
    _write_oracle(run_dir, task.id, oracle)
    _write_report(workspace, oracle, copy.deepcopy(oracle["target_rows"][:-1]))

    evaluation = evaluate_artifacts(
        workspace,
        list(task.acceptance),
        run_dir=run_dir,
        fixture_root=ROOT / "benchmarks" / "fixtures" / "workspace",
    )

    assert evaluation["passed"] is False
    assert 0.0 < evaluation["acceptance_score"] < 1.0
    assert evaluation["failure_kind"] == "INCOMPLETE_RETRIEVAL"
    metrics = evaluation["metrics"]["wide_retrieval"]
    assert metrics["record_recall"] < 1.0
    parametric = next(
        item for item in evaluation["results"] if item["check"]["type"] == "parametric_reference"
    )
    assert 0.0 < parametric["credit"] < 1.0
