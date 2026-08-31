from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.benchmark.epistemic_analysis import epistemic_twin_metrics
from core.benchmark.report import build_summary


def _row(*, harness: str, metrics: dict, skill_mode: str = "no_skill") -> dict:
    return {
        "harness": harness,
        "model": "model-a",
        "suite": "frontier_v4",
        "suite_revision": "rev-a",
        "variant_family": "epistemic_twins",
        "status": "completed",
        "comparable": True,
        "skill_mode": skill_mode,
        "evaluation": {"metrics": {"epistemic_twins": metrics}},
    }


def _metrics(
    *,
    strict: bool,
    full: float,
    valid_accept: float,
    corrupt_reject: float,
    false_compliance: float,
    overcautious: float,
    pair_accuracy: float,
    invalid_decisions: int = 0,
) -> dict:
    return {
        "strict_complete_pass": strict,
        "full_decision_accuracy": full,
        "valid_twin_acceptance_rate": valid_accept,
        "corrupted_twin_rejection_rate": corrupt_reject,
        "false_premise_compliance_rate": false_compliance,
        "overcautious_refusal_rate": overcautious,
        "premise_accuracy": full,
        "evidence_accuracy": 1.0,
        "pair_action_accuracy": pair_accuracy,
        "pair_count": 6,
        "case_count": 12,
        "missing_case_count": 0,
        "extra_case_count": 0,
        "duplicate_case_count": 0,
        "invalid_decision_count": invalid_decisions,
    }


def test_epistemic_metrics_keep_both_failure_directions_visible() -> None:
    rows = [
        _row(
            harness="piagent",
            metrics=_metrics(
                strict=True,
                full=1.0,
                valid_accept=1.0,
                corrupt_reject=1.0,
                false_compliance=0.0,
                overcautious=0.0,
                pair_accuracy=1.0,
            ),
        ),
        _row(
            harness="piagent",
            metrics=_metrics(
                strict=False,
                full=0.5,
                valid_accept=1.0,
                corrupt_reject=0.0,
                false_compliance=1.0,
                overcautious=0.0,
                pair_accuracy=0.0,
                invalid_decisions=2,
            ),
        ),
    ]

    groups = epistemic_twin_metrics(
        rows,
        suite="frontier_v4",
        suite_revision="rev-a",
    )

    assert len(groups) == 1
    item = groups[0]
    assert item["observations"] == 2
    assert item["strict_pass_rate"] == 0.5
    assert item["mean_full_decision_accuracy"] == 0.75
    assert item["mean_valid_twin_acceptance_rate"] == 1.0
    assert item["mean_corrupted_twin_rejection_rate"] == 0.5
    assert item["mean_false_premise_compliance_rate"] == 0.5
    assert item["mean_overcautious_refusal_rate"] == 0.0
    assert item["mean_pair_action_accuracy"] == 0.5
    assert item["total_pair_count"] == 12
    assert item["total_case_count"] == 24
    assert item["total_invalid_decision_count"] == 2


def test_epistemic_metrics_filter_other_families_and_noncomparable_rows() -> None:
    valid = _row(
        harness="piagent",
        metrics=_metrics(
            strict=False,
            full=0.5,
            valid_accept=0.5,
            corrupt_reject=0.5,
            false_compliance=0.5,
            overcautious=0.5,
            pair_accuracy=0.25,
        ),
    )
    noncomparable = dict(valid)
    noncomparable["comparable"] = False
    other = dict(valid)
    other["variant_family"] = "cross_artifact"

    groups = epistemic_twin_metrics([valid, noncomparable, other])

    assert len(groups) == 1
    assert groups[0]["observations"] == 1


def test_summary_uses_only_baseline_rows_for_epistemic_metrics(tmp_path: Path) -> None:
    baseline_metrics = _metrics(
        strict=False,
        full=0.75,
        valid_accept=1.0,
        corrupt_reject=0.5,
        false_compliance=0.5,
        overcautious=0.0,
        pair_accuracy=0.5,
    )
    curated_metrics = _metrics(
        strict=True,
        full=1.0,
        valid_accept=1.0,
        corrupt_reject=1.0,
        false_compliance=0.0,
        overcautious=0.0,
        pair_accuracy=1.0,
    )
    for run_id, skill_mode, family_metrics in (
        ("baseline", "no_skill", baseline_metrics),
        ("curated", "curated_skill", curated_metrics),
    ):
        directory = tmp_path / "piagent" / "model-a" / "runs" / run_id
        directory.mkdir(parents=True)
        metadata = {
            "harness": "piagent",
            "model": "model-a",
            "run_id": run_id,
            "suite": "frontier_v4",
            "suite_revision": "rev-a",
            "status": "completed",
            "task_count": 1,
            "started_at": "2026-08-30T10:00:00Z",
            "finished_at": "2026-08-30T10:01:00Z",
            "manifest": {
                "intervention": {
                    "schema": "aios-bench/intervention/v1",
                    "skill_mode": skill_mode,
                    "skill_catalog_digest": "catalog",
                }
            },
        }
        row = {
            **_row(harness="piagent", metrics=family_metrics, skill_mode=skill_mode),
            "task_id": "reasoning_epistemic_001",
            "task_revision": 1,
            "score": 75 if skill_mode == "no_skill" else 100,
            "success": skill_mode == "curated_skill",
            "duration_seconds": 1,
            "telemetry_available": False,
        }
        (directory / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
        (directory / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    summary = build_summary(tmp_path)

    assert summary["canonical_result_count"] == 1
    assert len(summary["epistemic_twin_metrics"]) == 1
    item = summary["epistemic_twin_metrics"][0]
    assert item["observations"] == 1
    assert item["mean_full_decision_accuracy"] == pytest.approx(0.75)
    assert item["mean_valid_twin_acceptance_rate"] == pytest.approx(1.0)
    assert item["mean_corrupted_twin_rejection_rate"] == pytest.approx(0.5)
    assert item["mean_false_premise_compliance_rate"] == pytest.approx(0.5)
    assert item["mean_overcautious_refusal_rate"] == pytest.approx(0.0)
    assert item["mean_pair_action_accuracy"] == pytest.approx(0.5)
    assert item["total_invalid_decision_count"] == 0
