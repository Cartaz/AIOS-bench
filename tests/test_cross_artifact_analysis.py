from __future__ import annotations

import json
from pathlib import Path

import pytest

from aios_bench.cross_artifact_analysis import cross_artifact_metrics
from aios_bench.report import build_summary


def _row(
    *,
    machine: float,
    human: float,
    reconciliation: float,
    strict: bool,
    skill_mode: str = "no_skill",
) -> dict:
    return {
        "harness": "piagent",
        "model": "ornith",
        "suite": "frontier_v4",
        "suite_revision": "revision-v45",
        "variant_family": "cross_artifact",
        "skill_mode": skill_mode,
        "status": "completed" if strict else "failed",
        "comparable": True,
        "evaluation": {
            "metrics": {
                "cross_artifact": {
                    "strict_complete_pass": strict,
                    "machine_accuracy": machine,
                    "human_accuracy": human,
                    "reconciliation_rate": reconciliation,
                    "machine_extra_groups": 0,
                    "human_extra_groups": 0,
                    "expected_groups": 6,
                    "machine_groups": 6,
                    "human_groups": 6,
                }
            }
        },
    }


def test_cross_artifact_analysis_aggregates_dimensions() -> None:
    output = cross_artifact_metrics([
        _row(machine=1.0, human=1.0, reconciliation=1.0, strict=True),
        _row(machine=0.9, human=0.8, reconciliation=0.75, strict=False),
    ])

    assert len(output) == 1
    item = output[0]
    assert item["observations"] == 2
    assert item["strict_pass_rate"] == 0.5
    assert item["mean_machine_accuracy"] == pytest.approx(0.95)
    assert item["mean_human_accuracy"] == pytest.approx(0.9)
    assert item["mean_reconciliation_rate"] == pytest.approx(0.875)
    assert item["total_expected_groups"] == 12


def test_summary_uses_only_baseline_rows_for_cross_artifact_metrics(tmp_path: Path) -> None:
    for run_id, skill_mode, metrics in (
        ("baseline", "no_skill", _row(machine=0.9, human=0.8, reconciliation=0.75, strict=False)),
        (
            "curated",
            "curated_skill",
            _row(machine=1.0, human=1.0, reconciliation=1.0, strict=True, skill_mode="curated_skill"),
        ),
    ):
        directory = tmp_path / "piagent" / "ornith" / "runs" / run_id
        directory.mkdir(parents=True)
        metadata = {
            "harness": "piagent",
            "model": "ornith",
            "run_id": run_id,
            "suite": "frontier_v4",
            "suite_revision": "revision-v45",
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
            "task_id": "data_cross_artifact_001",
            "task_revision": 1,
            "score": 82 if skill_mode == "no_skill" else 100,
            "success": skill_mode == "curated_skill",
            "duration_seconds": 1,
            "telemetry_available": False,
        }
        (directory / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
        (directory / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    summary = build_summary(tmp_path)

    assert summary["canonical_result_count"] == 1
    assert len(summary["cross_artifact_metrics"]) == 1
    item = summary["cross_artifact_metrics"][0]
    assert item["observations"] == 1
    assert item["mean_machine_accuracy"] == pytest.approx(0.9)
    assert item["mean_human_accuracy"] == pytest.approx(0.8)
    assert item["mean_reconciliation_rate"] == pytest.approx(0.75)
