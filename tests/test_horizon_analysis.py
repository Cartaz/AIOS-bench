from __future__ import annotations

import json
from pathlib import Path

from aios_bench.horizon import get_horizon_profile
from aios_bench.horizon_analysis import long_horizon_response_curves
from aios_bench.report import build_summary


def _row(
    cell,
    profile,
    *,
    repeat: int = 1,
    task_seed: int = 7001,
    success: bool = True,
    score: float = 100.0,
    skill_mode: str = "no_skill",
    parameters: dict | None = None,
    status: str = "completed",
    comparable: bool = True,
) -> dict:
    return {
        "harness": "piagent",
        "agent": "piagent",
        "model": "model-a",
        "suite": "frontier_v4",
        "suite_revision": "rev-horizon",
        "run_id": f"run-{cell.id}-{skill_mode}",
        "task_id": cell.task_id,
        "variant_family": cell.family,
        "variant_parameters": parameters if parameters is not None else dict(cell.parameters),
        "variant_digest": f"variant-{cell.id}-r{repeat}",
        "execution_fingerprint": f"execution-{cell.id}",
        "landscape_execution_fingerprint": "landscape-profile",
        "model_identity_fingerprint": "model-fingerprint",
        "model_strictly_comparable": True,
        "experiment_id": "horizon-exp",
        "schedule_mode": "pressure_sweep_sequential",
        "experiment_context": profile.context_for(cell),
        "repeat": repeat,
        "task_seed": task_seed,
        "orchestration_seed": 42,
        "skill_mode": skill_mode,
        "status": status,
        "comparable": comparable,
        "success": success,
        "score": score,
        "duration_seconds": 10.0 + cell.path_index,
        "input_tokens": 100 * cell.path_index,
        "output_tokens": 20 * cell.path_index,
        "failure_kind": "PASS" if success else "WRONG",
    }


def test_long_horizon_curve_preserves_exact_order_and_seed_control() -> None:
    profile = get_horizon_profile()
    cells = profile.family_cells("stateful_world")
    rows = [_row(cell, profile, score=100 - 20 * (cell.path_index - 1)) for cell in cells]

    curves = long_horizon_response_curves(
        rows,
        suite="frontier_v4",
        suite_revision="rev-horizon",
    )

    assert len(curves) == 1
    curve = curves[0]
    assert curve["profile_id"] == profile.id
    assert curve["profile_digest"] == profile.digest
    assert curve["variant_family"] == "stateful_world"
    assert curve["complete_cell_coverage"] is True
    assert curve["parameter_identity_consistent"] is True
    assert curve["seed_control_consistent"] is True
    assert [cell["path_index"] for cell in curve["response_curve"]] == [1, 2, 3]
    assert [cell["mean_score"] for cell in curve["response_curve"]] == [100, 80, 60]
    assert "not an assumed monotonic difficulty curve" in curve["interpretation"]


def test_long_horizon_curve_reports_missing_cell_and_parameter_mismatch() -> None:
    profile = get_horizon_profile()
    cells = profile.family_cells("wide_retrieval")
    bad_parameters = dict(cells[0].parameters)
    bad_parameters["corpus_size"] += 1
    rows = [
        _row(cells[0], profile, parameters=bad_parameters),
        _row(cells[2], profile),
    ]

    curve = long_horizon_response_curves(rows)[0]

    assert curve["complete_cell_coverage"] is False
    assert curve["missing_cell_ids"] == [cells[1].id]
    assert curve["parameter_identity_consistent"] is False


def test_long_horizon_curve_detects_seed_drift_within_repeat() -> None:
    profile = get_horizon_profile()
    cells = profile.family_cells("workspace_lineage")
    rows = [
        _row(cells[0], profile, task_seed=111),
        _row(cells[1], profile, task_seed=222),
        _row(cells[2], profile, task_seed=111),
    ]

    curve = long_horizon_response_curves(rows)[0]

    assert curve["seed_control_consistent"] is False


def test_long_horizon_curve_keeps_unsupported_cells_visible() -> None:
    profile = get_horizon_profile()
    cells = profile.family_cells("tool_recovery")
    rows = [
        _row(cells[0], profile),
        _row(cells[1], profile, status="unsupported", comparable=False, success=False, score=0),
        _row(cells[2], profile),
    ]

    curve = long_horizon_response_curves(rows)[0]
    middle = curve["response_curve"][1]

    assert curve["complete_cell_coverage"] is True
    assert middle["unsupported_observations"] == 1
    assert middle["comparable_observations"] == 0
    assert middle["pass_rate"] is None


def _write_run(root: Path, row: dict, *, started: str) -> None:
    directory = root / row["harness"] / row["model"] / "runs" / row["run_id"]
    directory.mkdir(parents=True)
    metadata = {
        "harness": row["harness"],
        "model": row["model"],
        "run_id": row["run_id"],
        "suite": row["suite"],
        "suite_revision": row["suite_revision"],
        "status": "completed",
        "task_count": 1,
        "started_at": started,
        "finished_at": started,
        "experiment_context": row["experiment_context"],
        "manifest": {
            "intervention": {
                "schema": "aios-bench/intervention/v1",
                "skill_mode": row["skill_mode"],
                "skill_catalog_digest": "catalog",
            }
        },
    }
    (directory / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    (directory / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_summary_reports_horizon_curves_without_polluting_canonical_leaderboard(
    tmp_path: Path,
) -> None:
    profile = get_horizon_profile()
    cells = profile.family_cells("dependency_world")
    for index, cell in enumerate(cells, 1):
        baseline = _row(cell, profile, skill_mode="no_skill")
        baseline["run_id"] = f"baseline-{cell.id}"
        _write_run(tmp_path, baseline, started=f"2026-08-31T0{index}:00:00Z")

        curated = _row(cell, profile, skill_mode="curated_skill")
        curated["run_id"] = f"curated-{cell.id}"
        _write_run(tmp_path, curated, started=f"2026-08-31T0{index}:30:00Z")

    summary = build_summary(tmp_path)

    assert summary["canonical_result_count"] == 0
    assert summary["leaderboard"] == []
    assert summary["selected_suite"] is None
    reasons = {run["eligibility_reason"] for run in summary["runs"]}
    assert reasons == {"pressure_profile", "experimental_intervention"}
    assert len(summary["long_horizon_response_curves"]) == 1
    curve = summary["long_horizon_response_curves"][0]
    assert curve["observed_cells"] == 3
    assert curve["complete_cell_coverage"] is True
