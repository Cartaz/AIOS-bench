from __future__ import annotations

import json
from pathlib import Path

from aios_bench.horizon import HORIZON_CONTEXT_KIND
from aios_bench.report import write_summary
from aios_bench.statistics import augment_summary_file


def _write_run(
    root: Path,
    *,
    harness: str,
    run_id: str,
    experiment_id: str,
    score: float,
    success: bool,
    failure_kind: str,
    horizon: bool,
) -> None:
    directory = root / harness / "model-a" / "runs" / run_id
    directory.mkdir(parents=True)
    context = {"kind": HORIZON_CONTEXT_KIND} if horizon else None
    metadata = {
        "harness": harness,
        "model": "model-a",
        "run_id": run_id,
        "suite": "frontier_v4",
        "suite_revision": "rev-v4",
        "status": "completed",
        "task_count": 1,
        "started_at": "2026-08-31T06:00:00Z",
        "finished_at": "2026-08-31T06:01:00Z",
        "execution_fingerprint": f"execution-{harness}",
    }
    if context is not None:
        metadata["experiment_context"] = context
    (directory / "run.json").write_text(json.dumps(metadata), encoding="utf-8")

    row = {
        "harness": harness,
        "agent": harness,
        "model": "model-a",
        "run_id": run_id,
        "suite": "frontier_v4",
        "suite_revision": "rev-v4",
        "task_id": "stateful_support_001",
        "repeat": 1,
        "orchestration_seed": 42,
        "task_seed": 1234,
        "experiment_id": experiment_id,
        "schedule_mode": "matched_interleaved",
        "model_identity_fingerprint": "model-fingerprint",
        "model_strictly_comparable": True,
        "skill_mode": "no_skill",
        "status": "completed",
        "comparable": True,
        "success": success,
        "score": score,
        "failure_kind": failure_kind,
        "usage_source": "server_verified",
        "server_usage": {
            "trusted_for_efficiency": True,
            "prompt_tokens": 100,
            "output_tokens": 20,
            "prompt_seconds": 2.0,
            "generation_seconds": 1.0,
        },
    }
    if context is not None:
        row["experiment_context"] = context
    (directory / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_derived_statistics_exclude_long_horizon_pressure_runs(tmp_path: Path) -> None:
    for harness, score in (("hermes", 80.0), ("piagent", 70.0)):
        _write_run(
            tmp_path,
            harness=harness,
            run_id=f"ordinary-{harness}",
            experiment_id="ordinary-exp",
            score=score,
            success=True,
            failure_kind="PASS",
            horizon=False,
        )
        _write_run(
            tmp_path,
            harness=harness,
            run_id=f"horizon-{harness}",
            experiment_id="horizon-exp",
            score=0.0,
            success=False,
            failure_kind="WRONG",
            horizon=True,
        )

    summary_path = write_summary(tmp_path)
    augment_summary_file(summary_path, tmp_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert len(summary["repeat_groups"]) == 2
    assert all(group["attempts"] == 1 for group in summary["repeat_groups"])

    assert len(summary["paired_comparisons"]) == 1
    comparison = summary["paired_comparisons"][0]
    assert comparison["experiment_id"] == "ordinary-exp"
    assert comparison["matched_observations"] == 1

    assert len(summary["failure_distributions"]) == 2
    assert all(group["counts"] == {"PASS": 1} for group in summary["failure_distributions"])

    assert len(summary["server_efficiency"]) == 2
    assert all(group["server_verified_tasks"] == 1 for group in summary["server_efficiency"])
