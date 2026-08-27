from __future__ import annotations

import json
from pathlib import Path

from core.benchmark.dashboard import build_dashboard
from core.benchmark.report import build_summary


def _event(kind: str, **data: object) -> dict[str, object]:
    return {"type": kind, "source": "test", "data": data}


def _write_run(root: Path) -> None:
    run_dir = root / "piagent" / "model-a" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    metadata = {
        "harness": "piagent",
        "model": "model-a",
        "run_id": "run-1",
        "suite": "frontier-v4",
        "suite_revision": "rev-1",
        "execution_fingerprint": "fp-1",
        "status": "completed",
        "task_count": 1,
        "started_at": "2026-08-27T05:00:00Z",
        "finished_at": "2026-08-27T05:01:00Z",
    }
    row = {
        "task_id": "task-1",
        "status": "completed",
        "comparable": True,
        "success": True,
        "score": 100,
        "duration_seconds": 60.0,
        "output_tokens": 300,
        "events": [
            _event("assistant_message", turn=True),
            _event("tool_call", tool="read"),
            _event("tool_result", tool="read", is_error=False),
            _event("tool_call", tool="edit"),
            _event("file_read"),
            _event("file_write"),
        ],
        "client_resources": {
            "available": True,
            "process_tree": {
                "rss_baseline_bytes": 100 * 1024 * 1024,
                "rss_peak_bytes": 160 * 1024 * 1024,
                "rss_peak_delta_bytes": 60 * 1024 * 1024,
                "cpu_mean_percent": 12.5,
            },
        },
    }
    (run_dir / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_summary_exposes_behavior_and_resource_efficiency_without_score_mixing(tmp_path: Path) -> None:
    _write_run(tmp_path)

    summary = build_summary(tmp_path)

    behavior = summary["agent_behavior_efficiency"]
    resources = summary["resource_efficiency"]
    assert len(behavior) == 1
    assert behavior[0]["tasks_with_behavior_telemetry"] == 1
    assert behavior[0]["mean_tool_calls"] == 2.0
    assert behavior[0]["mean_file_reads"] == 1.0
    assert behavior[0]["affects_score"] is False
    assert len(resources) == 1
    assert resources[0]["client"]["rss_peak_task_mean_bytes"] == 160 * 1024 * 1024
    assert summary["leaderboard"][0]["mean_score"] == 100.0


def test_dashboard_renders_agent_behavior_and_uses_summary_resource_data(tmp_path: Path) -> None:
    _write_run(tmp_path)

    dashboard = build_dashboard(tmp_path).read_text(encoding="utf-8")

    assert "Agent trajectory behavior" in dashboard
    assert "No reliable structured trajectory telemetry yet." not in dashboard
    assert "Mean tool calls" in dashboard
    assert ">2.0<" in dashboard
    assert "Client resource cost" in dashboard
    assert "160.0 MiB" in dashboard
