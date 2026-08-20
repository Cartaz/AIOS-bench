from __future__ import annotations

import json
from pathlib import Path

import pytest

from aios_bench.report import build_summary, load_results, write_summary


def _run(
    root: Path,
    run_id: str,
    *,
    suite: str = "frontier_v3",
    revision: str = "revision-a",
    status: str | None = "completed",
    started_at: str = "2026-08-20T10:00:00Z",
    finished_at: str | None = "2026-08-20T10:05:00Z",
    task_count: int = 1,
    model: str = "model",
    rows: list[dict] | None = None,
    dry_run: bool = False,
) -> Path:
    directory = root / "agent" / model / "runs" / run_id
    directory.mkdir(parents=True)
    metadata = {
        "harness": "agent",
        "model": model,
        "run_id": run_id,
        "suite": suite,
        "suite_revision": revision,
        "task_count": task_count,
        "started_at": started_at,
        "dry_run": dry_run,
    }
    if status is not None:
        metadata["status"] = status
    if finished_at is not None:
        metadata["finished_at"] = finished_at
    (directory / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    if rows is not None:
        (directory / "results.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
    return directory


def _result(task_id: str, score: float | None, **values: object) -> dict:
    return {
        "harness": "untrusted-row-harness",
        "model": "untrusted-row-model",
        "run_id": "untrusted-row-run",
        "suite": "untrusted-row-suite",
        "suite_revision": "untrusted-row-revision",
        "task_id": task_id,
        "task_revision": 1,
        "status": "completed",
        "success": True,
        "score": score,
        "duration_seconds": 12,
        "telemetry_available": True,
        "category": "coding",
        "tier": 3,
        **values,
    }


def test_results_are_deduplicated_with_manifest_identity(tmp_path: Path) -> None:
    replacement = _result("task-1", 90)
    replacement["task_revision"] = 2
    _run(
        tmp_path,
        "run-a",
        rows=[_result("task-1", 10, success=False), replacement],
    )

    rows = load_results(tmp_path)
    summary = build_summary(tmp_path)

    assert len(rows) == 1
    assert rows[0]["score"] == 90
    assert rows[0]["harness"] == "agent"
    assert rows[0]["run_id"] == "run-a"
    assert summary["result_count"] == 1
    assert summary["runs"][0]["tasks"] == 1
    assert summary["runs"][0]["mean_score"] == 90


def test_suite_revision_is_part_of_identity_and_old_revision_is_history(tmp_path: Path) -> None:
    _run(
        tmp_path, "shared-id", revision="revision-a", model="model-a",
        started_at="2026-08-20T09:00:00Z", rows=[_result("task", 10)],
    )
    _run(
        tmp_path, "shared-id", revision="revision-b", model="model-b",
        started_at="2026-08-20T10:00:00Z", rows=[_result("task", 20)],
    )
    # Force the same harness/model/run id despite separate storage directories.
    for path in tmp_path.rglob("run.json"):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["model"] = "same-model"
        path.write_text(json.dumps(metadata), encoding="utf-8")

    summary = build_summary(tmp_path)

    assert summary["result_count"] == 2
    assert {run["suite_revision"] for run in summary["runs"]} == {"revision-a", "revision-b"}
    assert summary["selected_suite"] == "frontier_v3"
    assert summary["selected_suite_revision"] == "revision-b"
    assert [run["suite_revision"] for run in summary["leaderboard"]] == ["revision-b"]


def test_unsupported_is_visible_but_excluded_from_denominators(tmp_path: Path) -> None:
    _run(
        tmp_path,
        "complete",
        task_count=3,
        rows=[
            _result("pass", 80),
            _result("fail", 20, success=False, telemetry_available=False),
            _result(
                "unsupported",
                None,
                status="unsupported",
                success=False,
                duration_seconds=999,
            ),
        ],
    )

    run = build_summary(tmp_path)["runs"][0]

    assert run["complete"] is True
    assert run["eligible"] is True
    assert run["tasks"] == 3
    assert run["comparable_tasks"] == 2
    assert run["unsupported"] == 1
    assert run["passed"] == 1
    assert run["success_rate"] == 50
    assert run["mean_score"] == 50
    assert run["runtime_seconds"] == 24
    assert run["telemetry_rate"] == 50


def test_blocked_is_distinct_from_unsupported(tmp_path: Path) -> None:
    _run(
        tmp_path, "blocked-chain", task_count=2,
        rows=[
            _result("failed-parent", 49, success=False, status="failed"),
            _result("blocked-child", None, success=False, status="blocked", comparable=False),
        ],
    )
    run = build_summary(tmp_path)["runs"][0]
    assert run["unsupported"] == 0
    assert run["blocked"] == 1
    assert run["noncomparable"] == 1
    assert run["comparable_tasks"] == 1


def test_latest_uses_metadata_and_filters_ineligible_runs(tmp_path: Path) -> None:
    _run(
        tmp_path,
        "zzz-older",
        started_at="2026-08-20T08:00:00Z",
        finished_at="2026-08-20T08:10:00Z",
        rows=[_result("task", 10)],
    )
    _run(
        tmp_path,
        "aaa-newer",
        started_at="2026-08-20T09:00:00Z",
        finished_at="2026-08-20T09:10:00Z",
        rows=[_result("task", 90)],
    )
    _run(
        tmp_path,
        "newest-but-running",
        status="running",
        started_at="2026-08-20T10:00:00Z",
        finished_at=None,
        rows=[_result("task", 100)],
    )
    _run(tmp_path, "dryrun-newest", dry_run=True, rows=[_result("task", 100)])
    _run(tmp_path, "legacy", suite="legacy", revision="legacy", rows=[_result("task", 100)])
    _run(tmp_path, "empty-running", status="running", finished_at=None, rows=None)

    summary = build_summary(tmp_path)

    assert [run["run_id"] for run in summary["leaderboard"]] == ["aaa-newer"]
    assert {run["run_id"] for run in summary["runs"]} == {
        "zzz-older", "aaa-newer", "newest-but-running", "dryrun-newest", "legacy", "empty-running"
    }
    reasons = {run["run_id"]: run["eligibility_reason"] for run in summary["runs"]}
    assert reasons["newest-but-running"] == "incomplete"
    assert reasons["dryrun-newest"] == "dry_run"
    assert reasons["legacy"] == "legacy"


def test_new_incomplete_revision_does_not_fall_back_to_old_revision(tmp_path: Path) -> None:
    _run(
        tmp_path,
        "old-complete",
        revision="old-revision",
        started_at="2026-08-20T09:00:00Z",
        rows=[_result("task", 80)],
    )
    _run(
        tmp_path,
        "new-running",
        revision="new-revision",
        status="running",
        started_at="2026-08-20T10:00:00Z",
        finished_at=None,
        rows=[_result("task", 90)],
    )

    summary = build_summary(tmp_path)

    assert summary["selected_suite_revision"] == "new-revision"
    assert summary["leaderboard"] == []


def test_historical_manifest_without_lifecycle_status_stays_in_history(tmp_path: Path) -> None:
    _run(tmp_path, "historical", status=None, task_count=1, rows=[_result("task", 50)])
    _run(
        tmp_path,
        "historical-partial",
        status=None,
        task_count=2,
        rows=[_result("task", 50)],
    )

    runs = {run["run_id"]: run for run in build_summary(tmp_path)["runs"]}

    assert runs["historical"]["complete"] is False
    assert runs["historical"]["eligible"] is False
    assert runs["historical"]["eligibility_reason"] == "incomplete"
    assert runs["historical-partial"]["complete"] is False


def test_none_score_does_not_crash_or_bias_mean(tmp_path: Path) -> None:
    _run(
        tmp_path,
        "none-score",
        task_count=2,
        rows=[_result("not-scored", None), _result("scored", 75)],
    )

    run = build_summary(tmp_path)["runs"][0]

    assert run["comparable_tasks"] == 2
    assert run["scored_tasks"] == 1
    assert run["mean_score"] == pytest.approx(75)


def test_summary_can_be_published_outside_raw_results(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    published = tmp_path / "published"
    _run(raw, "run", rows=[_result("task", 75)])

    output = write_summary(raw, output_dir=published)

    assert output == published / "summary.json"
    assert output.is_file()
    assert not (raw / "summary.json").exists()
