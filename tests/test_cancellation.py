from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from core.benchmark import task_execution
from core.cancellation import CancellationToken, RunCancelled
from core.run_service import BenchmarkService, RunRequest

ROOT = Path(__file__).resolve().parents[1]


class _Process:
    returncode = -15

    def poll(self):
        return None

    def wait(self, timeout=None):
        return self.returncode


def test_cancellation_token_is_thread_safe_signal() -> None:
    token = CancellationToken()
    assert token.is_cancelled is False
    token.cancel()
    assert token.is_cancelled is True
    with pytest.raises(RunCancelled):
        token.raise_if_cancelled()


def test_process_polling_reports_cancel_and_always_cleans_owned_process(monkeypatch, tmp_path: Path) -> None:
    process = _Process()
    cleaned = []
    monkeypatch.setattr(task_execution, "spawn_owned", lambda *args, **kwargs: process)
    monkeypatch.setattr(task_execution, "terminate_owned", lambda proc: cleaned.append(proc))

    outcome = task_execution._run_process(
        ["fake-harness"],
        cwd=tmp_path,
        env={},
        stdout=StringIO(),
        stderr=StringIO(),
        timeout=30,
        runaway_check=None,
        cancellation_check=lambda: True,
    )

    assert outcome.cancelled is True
    assert outcome.timed_out is False
    assert cleaned == [process]


def test_service_returns_aborted_result_when_cancelled_before_execution(tmp_path: Path) -> None:
    service = BenchmarkService(ROOT)
    token = CancellationToken()
    token.cancel()
    request = RunRequest(
        suite="frontier_v3",
        harnesses=("piagent",),
        task_ids=("autonomy_001",),
        model="test",
        task_timeout=1,
    )
    events = []

    result = service.run(request, events.append, token)

    assert result["cancelled"] is True
    assert result["exit_code"] == 2
    assert result["summary"] is None
    assert events[-1]["type"] == "run_cancelled"
