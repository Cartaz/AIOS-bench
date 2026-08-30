from __future__ import annotations

import json
from pathlib import Path

import pytest

from aios_bench.report import build_summary
from aios_bench.retrieval_analysis import wide_retrieval_metrics


def _row(
    *,
    precision: float,
    recall: float,
    field_accuracy: float,
    provenance_recall: float,
    strict: bool,
    skill_mode: str = "no_skill",
) -> dict:
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "harness": "piagent",
        "model": "ornith",
        "suite": "frontier_v4",
        "suite_revision": "revision-v44",
        "variant_family": "wide_retrieval",
        "skill_mode": skill_mode,
        "status": "completed" if strict else "failed",
        "comparable": True,
        "evaluation": {
            "metrics": {
                "wide_retrieval": {
                    "strict_complete_pass": strict,
                    "record_precision": precision,
                    "record_recall": recall,
                    "record_f1": f1,
                    "field_accuracy": field_accuracy,
                    "provenance_recall": provenance_recall,
                    "expected_records": 12,
                    "predicted_rows": 12,
                    "missing_record_count": 1 if recall < 1 else 0,
                    "extra_record_count": 1 if precision < 1 else 0,
                    "duplicate_prediction_count": 0,
                    "wrong_authority_count": 1 if provenance_recall < 1 else 0,
                    "stale_source_count": 1 if provenance_recall < 1 else 0,
                    "mirror_source_count": 0,
                }
            }
        },
    }


def test_wide_retrieval_analysis_aggregates_distinct_metrics() -> None:
    output = wide_retrieval_metrics([
        _row(
            precision=1.0,
            recall=1.0,
            field_accuracy=1.0,
            provenance_recall=1.0,
            strict=True,
        ),
        _row(
            precision=0.8,
            recall=0.75,
            field_accuracy=0.9,
            provenance_recall=0.5,
            strict=False,
        ),
    ])

    assert len(output) == 1
    item = output[0]
    assert item["observations"] == 2
    assert item["strict_passes"] == 1
    assert item["strict_pass_rate"] == 0.5
    assert item["mean_record_precision"] == pytest.approx(0.9)
    assert item["mean_record_recall"] == pytest.approx(0.875)
    assert item["mean_field_accuracy"] == pytest.approx(0.95)
    assert item["mean_provenance_recall"] == pytest.approx(0.75)
    assert item["total_missing_record_count"] == 1
    assert item["total_extra_record_count"] == 1
    assert item["total_wrong_authority_count"] == 1
    assert item["total_stale_source_count"] == 1


def test_wide_retrieval_analysis_ignores_noncomparable_and_other_families() -> None:
    ignored = _row(
        precision=0,
        recall=0,
        field_accuracy=0,
        provenance_recall=0,
        strict=False,
    )
    ignored["comparable"] = False
    other = _row(
        precision=0,
        recall=0,
        field_accuracy=0,
        provenance_recall=0,
        strict=False,
    )
    other["variant_family"] = "expense_report"

    assert wide_retrieval_metrics([ignored, other]) == []


def test_summary_uses_only_baseline_rows_for_retrieval_metrics(tmp_path: Path) -> None:
    for run_id, skill_mode, metrics in (
        (
            "baseline",
            "no_skill",
            _row(
                precision=0.8,
                recall=0.75,
                field_accuracy=0.9,
                provenance_recall=0.5,
                strict=False,
            ),
        ),
        (
            "curated",
            "curated_skill",
            _row(
                precision=1,
                recall=1,
                field_accuracy=1,
                provenance_recall=1,
                strict=True,
                skill_mode="curated_skill",
            ),
        ),
    ):
        directory = tmp_path / "piagent" / "ornith" / "runs" / run_id
        directory.mkdir(parents=True)
        metadata = {
            "harness": "piagent",
            "model": "ornith",
            "run_id": run_id,
            "suite": "frontier_v4",
            "suite_revision": "revision-v44",
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
            **metrics,
            "task_id": "retrieval_wide_001",
            "task_revision": 1,
            "score": 49 if skill_mode == "no_skill" else 100,
            "success": skill_mode == "curated_skill",
            "duration_seconds": 1,
            "telemetry_available": False,
        }
        (directory / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
        (directory / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    summary = build_summary(tmp_path)

    assert summary["canonical_result_count"] == 1
    assert len(summary["wide_retrieval_metrics"]) == 1
    item = summary["wide_retrieval_metrics"][0]
    assert item["observations"] == 1
    assert item["strict_pass_rate"] == 0
    assert item["mean_record_precision"] == pytest.approx(0.8)
