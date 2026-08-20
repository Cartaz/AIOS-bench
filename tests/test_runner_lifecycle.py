from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from aios_bench.adapters import Adapter, AgentInvocation
from aios_bench.models import Task
from aios_bench.runner import AgentConfig, BenchmarkRunner


class CommandAdapter(Adapter):
    name = "testagent"

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        return AgentInvocation([sys.executable, "-c", "pass"], {}, requested_model=model, resolved_model=model)


class LifecycleRunner(BenchmarkRunner):
    def _suite_name(self) -> str:
        return "test_suite"

    def _current_suite_revision(self) -> str:
        return "test-revision"

    def _catalog_task_count(self) -> list[str]:
        return ["coding_001", "subagents_001"]


TASKS = [
    Task("coding_001", "coding", "Do it"),
    Task(
        "subagents_001", "subagents", "Delegate it",
        required_capabilities=("structured_subagent_events",),
    ),
]


def _runner(tmp_path: Path, **values) -> LifecycleRunner:
    return LifecycleRunner(
        Path(__file__).resolve().parents[1],
        AgentConfig("testagent", "Test Agent", CommandAdapter()),
        tmp_path,
        task_timeout=5,
        total_timeout=values.pop("total_timeout", None),
        model="test-model",
        run_id=values.pop("run_id", "run-1"),
        **values,
    )


def test_completed_lifecycle_records_unsupported_and_updates_latest(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AIOS_BENCH_SANDBOX", "off")
    runner = _runner(tmp_path)

    assert not (runner.model_dir / "latest").exists()
    initial = json.loads(runner.metadata_path.read_text())
    assert initial["status"] == "running"
    assert initial["manifest"]["configuration"]["runner_workspace_isolation"] == "disabled"
    assert len(initial["execution_fingerprint"]) == 64
    assert "git_dirty" in initial
    assert runner.run(TASKS) == 0

    metadata = json.loads(runner.metadata_path.read_text())
    rows = [json.loads(line) for line in runner.checkpoint.read_text().splitlines()]
    assert metadata["status"] == "completed"
    assert metadata["supported_task_count"] == 1
    assert metadata["unsupported_task_count"] == 1
    assert metadata["completed_task_count"] == 2
    assert {row["status"] for row in rows} == {"completed", "unsupported"}
    unsupported = next(row for row in rows if row["status"] == "unsupported")
    assert unsupported["score"] is None
    assert unsupported["comparable"] is False
    assert (runner.model_dir / "latest").resolve() == runner.run_dir.resolve()
    assert (runner.model_dir / "latest.txt").read_text().strip() == runner.run_id

    resumed = _runner(tmp_path)
    assert "finished_at" not in json.loads(resumed.metadata_path.read_text())
    assert not (resumed.model_dir / "latest").exists()
    assert not (resumed.model_dir / "latest.txt").exists()
    assert resumed.run(TASKS) == 0
    assert len(resumed.checkpoint.read_text().splitlines()) == 2


def test_aborted_run_never_becomes_latest(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AIOS_BENCH_SANDBOX", "off")
    runner = _runner(tmp_path, run_id="aborted", total_timeout=0)

    assert runner.run(TASKS[:1]) == 2
    assert json.loads(runner.metadata_path.read_text())["status"] == "aborted"
    assert not (runner.model_dir / "latest").exists()


def test_explicit_abort_finalizes_lifecycle(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AIOS_BENCH_SANDBOX", "off")
    runner = _runner(tmp_path, run_id="interrupted")
    runner.abort(TASKS)
    metadata = json.loads(runner.metadata_path.read_text())
    assert metadata["status"] == "aborted"
    assert "finished_at" in metadata


def test_no_resume_refuses_to_append_to_existing_run(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AIOS_BENCH_SANDBOX", "off")
    runner = _runner(tmp_path)
    assert runner.run(TASKS) == 0

    with pytest.raises(FileExistsError, match="already contains results"):
        _runner(tmp_path, resume=False)


def test_run_id_and_model_cannot_escape_results_root(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AIOS_BENCH_SANDBOX", "off")
    with pytest.raises(ValueError, match="run_id"):
        _runner(tmp_path, run_id="../../escape")

    runner = LifecycleRunner(
        Path(__file__).resolve().parents[1],
        AgentConfig("testagent", "Test Agent", CommandAdapter()),
        tmp_path, 5, None, model="../../model", run_id="safe",
    )
    assert runner.model_dir.parent == tmp_path / "testagent"

    long_model = "m" * 500
    bounded = LifecycleRunner(
        Path(__file__).resolve().parents[1],
        AgentConfig("testagent", "Test Agent", CommandAdapter()),
        tmp_path, 5, None, model=long_model, run_id="bounded",
    )
    assert len(bounded.model_dir.name) < 100


def test_incompatible_metadata_cannot_be_mixed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AIOS_BENCH_SANDBOX", "off")
    runner = _runner(tmp_path)
    metadata = json.loads(runner.metadata_path.read_text())
    metadata["suite_revision"] = "old-revision"
    runner.metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ValueError, match="incompatible metadata"):
        _runner(tmp_path)


def test_failed_dependency_blocks_warm_task_without_launching_agent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AIOS_BENCH_SANDBOX", "off")
    runner = _runner(tmp_path, run_id="dependency")
    prerequisite = Task("coding_001", "coding", "Fail")
    runner._write_result({
        **runner._result_identity(prerequisite), "status": "failed", "success": False,
        "score": 0, "comparable": True,
    })
    dependent = Task("coding_002", "coding", "Should not run", depends_on=("coding_001",))

    assert runner.run([dependent]) == 1
    latest = runner._latest_results()
    assert latest["coding_002"]["status"] == "blocked"
    assert latest["coding_002"]["score"] is None
