from __future__ import annotations

import json
import sys
from pathlib import Path

from core.benchmark.adapters import Adapter, AgentInvocation
from core.benchmark.harness_registry import AgentConfig
from core.benchmark.models import Task, Trajectory
from core.benchmark.runner import BenchmarkRunner


class _Adapter(Adapter):
    name = "cache-test"

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        return AgentInvocation(
            [sys.executable, "-c", "pass"],
            {},
            requested_model=model,
            resolved_model=model,
        )


class _Runner(BenchmarkRunner):
    def _suite_name(self) -> str:
        return "cache-suite"

    def _current_suite_revision(self) -> str:
        return "cache-revision"

    def _catalog_task_count(self) -> list[str]:
        return ["coding_001"]

    def run_task(self, task: Task, timeout: float) -> Trajectory:
        raise AssertionError("not used")


def _result(runner: _Runner, task: Task, *, success: bool) -> dict:
    return {
        **runner.result_identity(task),
        "status": "completed" if success else "failed",
        "success": success,
        "score": 100.0 if success else 0.0,
        "comparable": True,
    }


def test_checkpoint_index_is_reused_and_invalidated_by_external_change(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AIOS_BENCH_SANDBOX", "off")
    runner = _Runner(
        Path(__file__).resolve().parents[1],
        AgentConfig("cache-test", "Cache Test", _Adapter()),
        tmp_path,
        task_timeout=1,
        total_timeout=None,
        model="test",
        run_id="cache",
    )
    task = Task("coding_001", "coding", "test")
    runner.record_result(_result(runner, task, success=True))

    original_read_text = Path.read_text
    reads = 0

    def counted_read_text(path: Path, *args, **kwargs):
        nonlocal reads
        if path == runner.checkpoint:
            reads += 1
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted_read_text)
    assert runner._latest_results()[task.id]["success"] is True
    assert runner._latest_results()[task.id]["success"] is True
    assert reads == 0

    replacement = _result(runner, task, success=False)
    runner.checkpoint.write_text(json.dumps(replacement) + "\n", encoding="utf-8")
    assert runner._latest_results()[task.id]["success"] is False
    assert reads == 1
