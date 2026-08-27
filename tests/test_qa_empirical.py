from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from core.benchmark.qa_empirical import build_empirical_qa_evidence


def _task(task_id: str = "task_a", revision: int = 4):
    return SimpleNamespace(id=task_id, revision=revision)


def _write_run(
    root: Path,
    *,
    harness: str,
    model: str,
    run_id: str,
    task_id: str = "task_a",
    revision: int = 4,
    success: bool = True,
    score: float = 100.0,
    variant_parameters: dict | None = None,
    variant_digest: str | None = None,
    suite: str = "frontier_v4",
    comparable: bool = True,
    status: str = "completed",
    failure_kind: str | None = None,
) -> None:
    directory = root / harness / model / "runs" / run_id
    directory.mkdir(parents=True)
    (directory / "run.json").write_text(
        json.dumps({
            "harness": harness,
            "model": model,
            "run_id": run_id,
            "suite": suite,
            "suite_revision": "suite-rev",
            "status": "completed",
            "task_count": 1,
        }),
        encoding="utf-8",
    )
    (directory / "results.jsonl").write_text(
        json.dumps({
            "task_id": task_id,
            "task_revision": revision,
            "status": status,
            "failure_kind": failure_kind,
            "comparable": comparable,
            "success": success,
            "score": score,
            "variant_parameters": variant_parameters or {"pressure": 1},
            "variant_digest": variant_digest,
        }) + "\n",
        encoding="utf-8",
    )


def test_empirical_report_is_empty_without_current_revision_runs(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        harness="piagent",
        model="model-a",
        run_id="old",
        revision=3,
    )

    report = build_empirical_qa_evidence(tmp_path, [_task()])

    assert report["schema"] == "aios-bench/qa-empirical-evidence/v1"
    assert report["tasks_with_evidence"] == 0
    row = report["tasks"][0]
    assert row["eligible_attempts"] == 0
    assert row["outcome_distribution"] == "none"
    assert row["status_counts"] == {}
    assert row["failure_kind_counts"] == {}
    assert row["cross_profile_evidence_available"] is False
    assert row["collection_gaps"] == [
        "current_revision_attempt",
        "second_harness",
        "second_model",
        "second_variant",
    ]


def test_empirical_report_separates_profiles_models_harnesses_and_outcomes(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        harness="piagent",
        model="model-a",
        run_id="one",
        success=True,
        score=100,
        variant_parameters={"pressure": 1},
        variant_digest="variant-a",
    )
    _write_run(
        tmp_path,
        harness="claude",
        model="model-b",
        run_id="two",
        success=False,
        score=25,
        variant_parameters={"pressure": 2},
        variant_digest="variant-b",
        status="failed",
        failure_kind="deterministic_evaluation",
    )

    report = build_empirical_qa_evidence(tmp_path, [_task()])

    assert report["tasks_with_evidence"] == 1
    assert report["tasks_with_cross_profile_evidence"] == 1
    assert report["tasks_with_cross_harness_evidence"] == 1
    assert report["tasks_with_cross_model_evidence"] == 1
    assert report["tasks_with_mixed_outcomes"] == 1
    row = report["tasks"][0]
    assert row["eligible_attempts"] == 2
    assert row["distinct_profiles"] == 2
    assert row["distinct_harnesses"] == 2
    assert row["distinct_models"] == 2
    assert row["pass_count"] == 1
    assert row["fail_count"] == 1
    assert row["outcome_distribution"] == "mixed"
    assert row["status_counts"] == {"completed": 1, "failed": 1}
    assert row["failure_kind_counts"] == {"deterministic_evaluation": 1, "none": 1}
    assert row["success_rate"] == 0.5
    assert row["score_min"] == 25
    assert row["score_median"] == 62.5
    assert row["score_max"] == 100
    assert row["distinct_pressure_variants"] == 2
    assert row["distinct_variant_identities"] == 2
    assert row["collection_gaps"] == []
    assert report["collection_gap_counts"] == {
        "current_revision_attempt": 0,
        "second_harness": 0,
        "second_model": 0,
        "second_variant": 0,
    }
    assert "do not automatically pass" in report["interpretation"]


def test_variant_identity_uses_digest_even_when_pressure_coordinates_match(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        harness="piagent",
        model="model-a",
        run_id="one",
        variant_parameters={},
        variant_digest="seeded-a",
    )
    _write_run(
        tmp_path,
        harness="claude",
        model="model-b",
        run_id="two",
        variant_parameters={},
        variant_digest="seeded-b",
    )

    row = build_empirical_qa_evidence(tmp_path, [_task()])["tasks"][0]

    assert row["distinct_pressure_variants"] == 1
    assert row["distinct_variant_identities"] == 2
    assert "second_variant" not in row["collection_gaps"]


def test_failure_taxonomy_keeps_infrastructure_error_distinct_from_capability_failure(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        harness="piagent",
        model="model-a",
        run_id="capability-fail",
        success=False,
        score=0,
        status="failed",
        failure_kind="deterministic_evaluation",
    )
    _write_run(
        tmp_path,
        harness="claude",
        model="model-b",
        run_id="infra-error",
        success=False,
        score=0,
        status="error",
        failure_kind="runner_error",
    )

    row = build_empirical_qa_evidence(tmp_path, [_task()])["tasks"][0]

    assert row["fail_count"] == 2
    assert row["status_counts"] == {"error": 1, "failed": 1}
    assert row["failure_kind_counts"] == {
        "deterministic_evaluation": 1,
        "runner_error": 1,
    }


def test_empirical_report_excludes_noncomparable_and_other_suite_rows(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        harness="piagent",
        model="model-a",
        run_id="good",
        success=True,
    )
    _write_run(
        tmp_path,
        harness="claude",
        model="model-b",
        run_id="blocked",
        success=False,
        comparable=False,
    )
    _write_run(
        tmp_path,
        harness="opencode",
        model="model-c",
        run_id="v3",
        success=False,
        suite="frontier_v3",
    )

    report = build_empirical_qa_evidence(tmp_path, [_task()])

    row = report["tasks"][0]
    assert row["eligible_attempts"] == 1
    assert row["profiles"] == [{"harness": "piagent", "model": "model-a"}]
    assert row["outcome_distribution"] == "all_pass"
    assert row["collection_gaps"] == [
        "second_harness",
        "second_model",
        "second_variant",
    ]
