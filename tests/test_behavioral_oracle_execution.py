from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from core.benchmark.adapters import Adapter, AgentInvocation
from core.benchmark.models import Task
from core.benchmark.task_execution import run_frontier_task


class MutatingAdapter(Adapter):
    name = "testagent"

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        script = "from pathlib import Path; Path('keep.txt').write_text('changed', encoding='utf-8')"
        return AgentInvocation([sys.executable, "-c", script], {}, requested_model=model, resolved_model=model)


class FakeRunner:
    def __init__(self, root: Path) -> None:
        self.repo_root = root
        self.run_dir = root / "run"
        self.run_dir.mkdir()
        self.model = "model-a"
        self.run_id = "run-1"
        self.agent = SimpleNamespace(name="testagent", adapter=MutatingAdapter())
        self.resource_poll_interval = 0.01
        self.max_output_tokens = None
        self.metrics_poll_interval = 0.01
        self.written: dict | None = None

    def _workspace(self, task: Task) -> Path:
        workspace = self.run_dir / "workspaces" / task.id
        workspace.mkdir(parents=True)
        (workspace / "keep.txt").write_text("baseline", encoding="utf-8")
        return workspace

    def _result_identity(self, task: Task) -> dict[str, object]:
        return {
            "task_id": task.id,
            "category": task.category,
            "tier": task.tier,
            "task_revision": task.revision,
            "harness": self.agent.name,
            "model": self.model,
            "run_id": self.run_id,
            "suite": "test-suite",
            "suite_revision": "test-revision",
            "execution_fingerprint": "fp",
        }

    def _write_result(self, result: dict) -> None:
        self.written = result

    def _log(self, event: dict) -> None:
        pass


def _task() -> Task:
    return Task(
        "coding_001",
        "coding",
        "Change keep.txt",
        acceptance=({"type": "exists", "path": "keep.txt"},),
        behavioral_acceptance=({"type": "preserved_state", "path": "keep.txt"},),
    )


def test_behavioral_failure_is_persisted_but_does_not_change_capability_success(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("AIOS_BENCH_SANDBOX", "off")
    runner = FakeRunner(tmp_path)

    trajectory = run_frontier_task(runner, _task(), timeout=5)

    assert trajectory.success is True
    assert runner.written is not None
    result = runner.written
    assert result["success"] is True
    assert result["score"] == 100.0
    assert result["evaluation"]["passed"] is True
    assert result["behavioral_evaluation"]["passed"] is False
    assert result["behavioral_evaluation"]["affects_score"] is False
    sequences = [event["sequence"] for event in result["events"]]
    assert sequences == list(range(1, len(sequences) + 1))
    assert result["events"][-1]["type"] == "behavioral_evaluation"


def test_behavioral_evaluation_is_json_serializable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AIOS_BENCH_SANDBOX", "off")
    runner = FakeRunner(tmp_path)

    run_frontier_task(runner, _task(), timeout=5)

    assert runner.written is not None
    json.dumps(runner.written)
