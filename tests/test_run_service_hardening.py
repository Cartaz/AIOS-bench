from __future__ import annotations

from pathlib import Path

import pytest

from core.run_service import BenchmarkService, RunRequest

ROOT = Path(__file__).resolve().parents[1]


def _request(**overrides) -> RunRequest:
    values = {
        "suite": "frontier_v3",
        "harnesses": ("piagent",),
        "task_ids": ("autonomy_001",),
        "model": "test",
    }
    values.update(overrides)
    return RunRequest(**values)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("repeats", 1.5, "Repeats must be an integer"),
        ("repeats", True, "Repeats must be an integer"),
        ("task_timeout", float("nan"), "Task timeout must be greater than 0"),
        ("total_timeout", float("inf"), "Total timeout must be greater than 0"),
        ("max_output_tokens", 1.2, "Max output tokens must be an integer"),
        ("metrics_poll_interval", 0, "Metrics poll interval must be greater than 0"),
        ("resource_poll_interval", 0, "Resource poll interval must be greater than 0"),
        ("server_resource_url", 123, "Server resource URL must be a string or null"),
    ],
)
def test_run_request_rejects_invalid_runtime_types(field: str, value: object, message: str) -> None:
    service = BenchmarkService(ROOT)
    with pytest.raises(ValueError, match=message):
        service.validate_request(_request(**{field: value}))


def test_single_runner_unexpected_failure_aborts_run(monkeypatch) -> None:
    service = BenchmarkService(ROOT)

    class FailingRunner:
        aborted = False

        def run(self, tasks):
            raise RuntimeError("boom")

        def abort(self, tasks):
            self.aborted = True

    runner = FailingRunner()
    monkeypatch.setattr(service, "_build_runner", lambda *args, **kwargs: runner)

    with pytest.raises(RuntimeError, match="boom"):
        service.run(_request())

    assert runner.aborted is True


def test_abort_cleanup_continues_after_one_runner_fails(monkeypatch) -> None:
    service = BenchmarkService(ROOT)
    calls: list[str] = []

    class Runner:
        def __init__(self, name: str, fail: bool = False) -> None:
            self.name = name
            self.fail = fail

        def abort(self, tasks):
            calls.append(self.name)
            if self.fail:
                raise RuntimeError("cleanup failed")

    service._abort_runners({"first": Runner("first", True), "second": Runner("second")}, [])

    assert calls == ["first", "second"]
