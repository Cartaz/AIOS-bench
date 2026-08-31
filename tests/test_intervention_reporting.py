from __future__ import annotations

import json
from pathlib import Path

from aios_bench.dashboard import build_dashboard
from aios_bench.report import build_summary, canonical_capability_rows


def _write_arm(
    root: Path,
    *,
    run_id: str,
    mode: str,
    score: float,
    success: bool,
) -> None:
    run_dir = root / "piagent" / "ornith" / "runs" / run_id
    run_dir.mkdir(parents=True)
    metadata = {
        "harness": "piagent",
        "model": "ornith",
        "run_id": run_id,
        "suite": "frontier_v4",
        "suite_revision": "v43-revision",
        "status": "completed",
        "task_count": 1,
        "started_at": "2026-08-30T10:00:00Z",
        "finished_at": "2026-08-30T10:01:00Z",
        "execution_fingerprint": f"execution-{mode}",
        "manifest": {
            "intervention": {
                "schema": "aios-bench/intervention/v1",
                "skill_mode": mode,
                "skill_catalog_digest": "catalog-digest",
            }
        },
    }
    row = {
        "harness": "piagent",
        "agent": "piagent",
        "model": "ornith",
        "run_id": run_id,
        "suite": "frontier_v4",
        "suite_revision": "v43-revision",
        "task_id": "tool_recovery_001",
        "task_revision": 1,
        "category": "tool_use",
        "tier": 5,
        "status": "completed" if success else "failed",
        "success": success,
        "score": score,
        "comparable": True,
        "duration_seconds": 1.0,
        "variant_family": "tool_recovery",
        "variant_parameters": {
            "case_count": 24,
            "required_actions": 5,
            "distractor_tools": 4,
            "transient_failures": 3,
            "incomplete_responses": 8,
        },
        "variant_digest": "variant-digest",
        "experiment_id": "skill-exp",
        "schedule_mode": "matched_interleaved",
        "repeat": 1,
        "task_seed": 123,
        "model_identity_fingerprint": "strict-model",
        "model_strictly_comparable": True,
        "ablation_execution_fingerprint": "ablation-profile",
        "execution_fingerprint": f"execution-{mode}",
        "skill_mode": mode,
        "skill_available": True,
        "skill_applied": mode == "curated_skill",
        "skill_id": "tool-recovery/v1",
        "skill_digest": "skill-digest",
        "input_tokens": 100 if mode == "no_skill" else 130,
        "output_tokens": 40 if mode == "no_skill" else 35,
        "failure_kind": "PASS" if success else "WRONG",
    }
    (run_dir / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_canonical_capability_rows_exclude_curated_interventions() -> None:
    rows = [
        {"task_id": "legacy"},
        {"task_id": "baseline", "skill_mode": "no_skill"},
        {"task_id": "curated", "skill_mode": "curated_skill"},
    ]

    assert [row["task_id"] for row in canonical_capability_rows(rows)] == [
        "legacy",
        "baseline",
    ]


def test_summary_and_dashboard_isolate_curated_skill_arm(tmp_path: Path) -> None:
    _write_arm(
        tmp_path,
        run_id="baseline-run",
        mode="no_skill",
        score=40,
        success=False,
    )
    _write_arm(
        tmp_path,
        run_id="curated-run",
        mode="curated_skill",
        score=100,
        success=True,
    )

    summary = build_summary(tmp_path)
    runs = {run["run_id"]: run for run in summary["runs"]}

    assert runs["baseline-run"]["eligible"] is True
    assert runs["curated-run"]["eligible"] is False
    assert runs["curated-run"]["eligibility_reason"] == "experimental_intervention"
    assert [run["run_id"] for run in summary["leaderboard"]] == ["baseline-run"]
    assert summary["canonical_result_count"] == 1
    assert len(summary["skill_ablations"]) == 1
    ablation = summary["skill_ablations"][0]
    assert ablation["matched_observations"] == 1
    assert ablation["mean_skill_lift"] == 60

    dashboard = build_dashboard(tmp_path).read_text(encoding="utf-8")
    leaderboard, rest = dashboard.split("<h2>Reliability across repeats</h2>", 1)
    assert "baseline-run" in leaderboard
    assert "curated-run" not in leaderboard
    assert "Curated skill ablations" in rest
    assert "tool-recovery/v1" in rest
    assert "60.0" in rest
    assert "experimental_intervention" in rest
