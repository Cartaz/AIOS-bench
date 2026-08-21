from __future__ import annotations

import json
from pathlib import Path

from aios_bench.dashboard import build_dashboard


def test_dashboard_escapes_untrusted_values_and_uses_no_inner_html(tmp_path: Path) -> None:
    run_dir = tmp_path / "agent" / "model" / "runs" / "run"
    run_dir.mkdir(parents=True)
    attack = '<img src=x onerror="alert(1)">'
    metadata = {
        "harness": attack,
        "model": "</script><script>alert(2)</script>",
        "run_id": "run",
        "suite": "frontier_v3",
        "suite_revision": "revision",
        "status": "completed",
        "task_count": 1,
        "started_at": "2026-08-20T10:00:00Z",
        "finished_at": "2026-08-20T10:01:00Z",
        "git_commit": attack,
    }
    row = {
        "task_id": "task",
        "task_revision": 1,
        "status": "completed",
        "success": True,
        "score": 100,
        "category": attack,
        "tier": attack,
    }
    (run_dir / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    dashboard = build_dashboard(tmp_path).read_text(encoding="utf-8")

    assert attack not in dashboard
    assert "</script><script>" not in dashboard
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in dashboard
    assert "&lt;/script&gt;&lt;script&gt;alert(2)&lt;/script&gt;" in dashboard
    assert "innerHTML" not in dashboard
    assert "<script" not in dashboard


def test_dashboard_history_keeps_incomplete_and_dry_runs_off_leaderboard(tmp_path: Path) -> None:
    def add(run_id: str, status: str, dry_run: bool = False) -> None:
        directory = tmp_path / "agent" / run_id / "runs" / run_id
        directory.mkdir(parents=True)
        metadata = {
            "harness": "agent",
            "model": "model",
            "run_id": run_id,
            "suite": "frontier_v3",
            "suite_revision": "revision",
            "status": status,
            "task_count": 1,
            "started_at": "2026-08-20T10:00:00Z",
            "dry_run": dry_run,
        }
        if status == "completed":
            metadata["finished_at"] = "2026-08-20T10:01:00Z"
        (directory / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
        (directory / "results.jsonl").write_text(
            json.dumps({"task_id": "task", "success": True, "score": 50}) + "\n",
            encoding="utf-8",
        )

    add("eligible-run", "completed")
    add("running-run", "running")
    add("dry-run", "completed", dry_run=True)

    dashboard = build_dashboard(tmp_path).read_text(encoding="utf-8")
    leaderboard, history = dashboard.split("<h2>Run history</h2>", 1)

    assert "eligible-run" in leaderboard
    assert "running-run" not in leaderboard
    assert "dry-run" not in leaderboard
    assert "eligible-run" in history
    assert "running-run" in history
    assert "dry-run" in history


def test_dashboard_renders_reliability_paired_failure_and_efficiency_panels(tmp_path: Path) -> None:
    for harness, score, success, failure in (
        ("hermes", 100, True, "PASS"),
        ("piagent", 80, False, "WRONG"),
    ):
        directory = tmp_path / harness / "model" / "runs" / "exp-r01"
        directory.mkdir(parents=True)
        metadata = {
            "harness": harness,
            "model": "ornith",
            "run_id": "exp-r01",
            "suite": "frontier_v3",
            "suite_revision": "revision",
            "execution_fingerprint": f"profile-{harness}",
            "status": "completed",
            "task_count": 1,
            "started_at": "2026-08-20T10:00:00Z",
            "finished_at": "2026-08-20T10:01:00Z",
        }
        row = {
            "task_id": "task_a",
            "task_revision": 1,
            "status": "completed" if success else "failed",
            "success": success,
            "score": score,
            "category": "coding",
            "tier": 3,
            "repeat": 1,
            "orchestration_seed": 42,
            "experiment_id": "exp",
            "schedule_mode": "matched_interleaved",
            "task_seed": 99,
            "model_identity_fingerprint": "same-model",
            "model_strictly_comparable": True,
            "failure_kind": failure,
            "usage_source": "server_verified",
            "server_usage": {
                "trusted_for_efficiency": True,
                "prompt_tokens": 100,
                "output_tokens": 20,
                "prompt_seconds": 2.0,
                "generation_seconds": 1.0,
            },
        }
        (directory / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
        (directory / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    dashboard = build_dashboard(tmp_path).read_text(encoding="utf-8")

    assert "Reliability across repeats" in dashboard
    assert "Paired harness comparisons" in dashboard
    assert "Failure taxonomy" in dashboard
    assert "Server-verified efficiency" in dashboard
    assert "PASS=1" in dashboard
    assert "WRONG=1" in dashboard
    assert "same-model" not in dashboard  # internal identity stays out of the presentation
    assert "20.0" in dashboard  # paired mean score delta and server generation tok/s


def test_dashboard_can_be_published_outside_raw_results(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    published = tmp_path / "published"

    output = build_dashboard(raw, output_dir=published)

    assert output == published / "dashboard.html"
    assert output.is_file()
    assert not (raw / "dashboard.html").exists()
