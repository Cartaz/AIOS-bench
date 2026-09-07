from __future__ import annotations

from types import SimpleNamespace

from aios_bench.processes import OwnedProcessOutcome
from aios_bench.runtime_readiness import RUNTIME_PROBE_MARKER, probe_runtime_readiness


class _Runner:
    def __init__(self, tmp_path):
        self.run_dir = tmp_path / "run"
        self.run_dir.mkdir()
        self.run_id = "run-1"
        self.task_timeout = 900.0
        self.model = "Ornith"
        self.agent = SimpleNamespace(name="goose", adapter=object())
        self.cancellation_check = None
        self.events = []

    def record_event(self, event):
        self.events.append(event)


def _prepared():
    return SimpleNamespace(command=["fake-harness"], environment={})


def test_runtime_probe_success_is_ready_unscored_and_cleans_workspace(monkeypatch, tmp_path):
    runner = _Runner(tmp_path)
    monkeypatch.setattr(
        "aios_bench.runtime_readiness.prepare_harness_process",
        lambda **kwargs: _prepared(),
    )
    observed = {}

    def fake_run_owned(command, **kwargs):
        observed.update(kwargs)
        kwargs["stdout"].write(f'{{"message":"{RUNTIME_PROBE_MARKER}"}}\n')
        kwargs["stdout"].flush()
        return OwnedProcessOutcome(returncode=0)

    monkeypatch.setattr("aios_bench.runtime_readiness.run_owned", fake_run_owned)

    result = probe_runtime_readiness(runner)

    assert result.ready is True
    assert result.kind == "ready"
    assert result.returncode == 0
    assert observed["stdin"] is not None
    assert not (runner.run_dir / "workspaces" / "_runtime_probe").exists()
    assert runner.events[-1]["event"] == "harness_runtime_probe"
    assert runner.events[-1]["status"] == "ready"


def test_runtime_probe_zero_exit_without_model_marker_is_blocked(monkeypatch, tmp_path):
    runner = _Runner(tmp_path)
    monkeypatch.setattr(
        "aios_bench.runtime_readiness.prepare_harness_process",
        lambda **kwargs: _prepared(),
    )

    def fake_run_owned(command, **kwargs):
        kwargs["stdout"].write("CLI exited without an inference result\n")
        kwargs["stdout"].flush()
        return OwnedProcessOutcome(returncode=0)

    monkeypatch.setattr("aios_bench.runtime_readiness.run_owned", fake_run_owned)

    result = probe_runtime_readiness(runner)

    assert result.ready is False
    assert result.kind == "invalid_probe_response"
    assert result.returncode == 0


def test_runtime_probe_timeout_becomes_blocked_not_a_scored_task(monkeypatch, tmp_path):
    runner = _Runner(tmp_path)
    monkeypatch.setattr(
        "aios_bench.runtime_readiness.prepare_harness_process",
        lambda **kwargs: _prepared(),
    )
    monkeypatch.setattr(
        "aios_bench.runtime_readiness.run_owned",
        lambda *args, **kwargs: OwnedProcessOutcome(returncode=-15, timed_out=True),
    )

    result = probe_runtime_readiness(runner)

    assert result.ready is False
    assert result.kind == "timeout"
    assert result.task_reason()["runtime_readiness"]["status"] == "blocked"
    assert result.task_reason()["runtime_readiness"]["kind"] == "timeout"
    assert runner.events[-1]["status"] == "blocked"


def test_runtime_probe_nonzero_exit_is_runtime_block(monkeypatch, tmp_path):
    runner = _Runner(tmp_path)
    monkeypatch.setattr(
        "aios_bench.runtime_readiness.prepare_harness_process",
        lambda **kwargs: _prepared(),
    )
    monkeypatch.setattr(
        "aios_bench.runtime_readiness.run_owned",
        lambda *args, **kwargs: OwnedProcessOutcome(returncode=2),
    )

    result = probe_runtime_readiness(runner)

    assert result.ready is False
    assert result.kind == "process_exit"
    assert result.returncode == 2
    assert result.message == "runtime probe exited with code 2"
