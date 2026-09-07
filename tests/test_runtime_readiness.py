from __future__ import annotations

import json
from types import SimpleNamespace

from aios_bench.processes import OwnedProcessOutcome
from aios_bench.runtime_readiness import (
    CLAUDE_BASH_PROBE_MARKER,
    RUNTIME_PROBE_MARKER,
    probe_runtime_readiness,
)


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


def _goose_message(role: str, text: str) -> str:
    return json.dumps(
        {
            "type": "message",
            "message": {
                "role": role,
                "content": [{"type": "text", "text": text}],
            },
        }
    ) + "\n"


def _claude_assistant(content: list[dict]) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": content},
        }
    ) + "\n"


def _claude_tool_result(call_id: str, text: str, *, is_error: bool = False) -> str:
    return json.dumps(
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "content": text,
                        "is_error": is_error,
                    }
                ],
            },
        }
    ) + "\n"


def test_runtime_probe_success_is_ready_unscored_and_cleans_workspace(monkeypatch, tmp_path):
    runner = _Runner(tmp_path)
    monkeypatch.setattr(
        "aios_bench.runtime_readiness.prepare_harness_process",
        lambda **kwargs: _prepared(),
    )
    observed = {}

    def fake_run_owned(command, **kwargs):
        observed.update(kwargs)
        kwargs["stdout"].write(_goose_message("assistant", RUNTIME_PROBE_MARKER))
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


def test_runtime_probe_reassembles_chunked_goose_assistant_marker(monkeypatch, tmp_path):
    runner = _Runner(tmp_path)
    monkeypatch.setattr(
        "aios_bench.runtime_readiness.prepare_harness_process",
        lambda **kwargs: _prepared(),
    )

    def fake_run_owned(command, **kwargs):
        split = len(RUNTIME_PROBE_MARKER) // 2
        kwargs["stdout"].write(_goose_message("assistant", RUNTIME_PROBE_MARKER[:split]))
        kwargs["stdout"].write(_goose_message("assistant", RUNTIME_PROBE_MARKER[split:]))
        kwargs["stdout"].flush()
        return OwnedProcessOutcome(returncode=0)

    monkeypatch.setattr("aios_bench.runtime_readiness.run_owned", fake_run_owned)

    result = probe_runtime_readiness(runner)

    assert result.ready is True
    assert result.kind == "ready"


def test_runtime_probe_does_not_accept_goose_prompt_echo_as_model_marker(monkeypatch, tmp_path):
    runner = _Runner(tmp_path)
    monkeypatch.setattr(
        "aios_bench.runtime_readiness.prepare_harness_process",
        lambda **kwargs: _prepared(),
    )

    def fake_run_owned(command, **kwargs):
        kwargs["stdout"].write(_goose_message("user", RUNTIME_PROBE_MARKER))
        kwargs["stdout"].write(_goose_message("assistant", "READY"))
        kwargs["stdout"].flush()
        return OwnedProcessOutcome(returncode=0)

    monkeypatch.setattr("aios_bench.runtime_readiness.run_owned", fake_run_owned)

    result = probe_runtime_readiness(runner)

    assert result.ready is False
    assert result.kind == "invalid_probe_response"


def test_claude_runtime_probe_requires_successful_bash_tool_result(monkeypatch, tmp_path):
    runner = _Runner(tmp_path)
    runner.agent = SimpleNamespace(name="claude", adapter=object())
    observed_prompt = {}

    def fake_prepare(**kwargs):
        observed_prompt["prompt"] = kwargs["prompt"]
        return _prepared()

    monkeypatch.setattr("aios_bench.runtime_readiness.prepare_harness_process", fake_prepare)

    def fake_run_owned(command, **kwargs):
        call_id = "bash-1"
        kwargs["stdout"].write(
            _claude_assistant(
                [{"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": "printf"}}]
            )
        )
        kwargs["stdout"].write(_claude_tool_result(call_id, CLAUDE_BASH_PROBE_MARKER))
        kwargs["stdout"].write(
            _claude_assistant([{"type": "text", "text": RUNTIME_PROBE_MARKER}])
        )
        kwargs["stdout"].flush()
        return OwnedProcessOutcome(returncode=0)

    monkeypatch.setattr("aios_bench.runtime_readiness.run_owned", fake_run_owned)

    result = probe_runtime_readiness(runner)

    assert "Use the Bash tool exactly once" in observed_prompt["prompt"]
    assert result.ready is True
    assert result.kind == "ready"


def test_claude_runtime_probe_blocks_when_bash_tool_fails(monkeypatch, tmp_path):
    runner = _Runner(tmp_path)
    runner.agent = SimpleNamespace(name="claude", adapter=object())
    monkeypatch.setattr(
        "aios_bench.runtime_readiness.prepare_harness_process",
        lambda **kwargs: _prepared(),
    )

    def fake_run_owned(command, **kwargs):
        call_id = "bash-1"
        kwargs["stdout"].write(
            _claude_assistant(
                [{"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": "printf"}}]
            )
        )
        kwargs["stdout"].write(
            _claude_tool_result(
                call_id,
                "bwrap: Can't create file /home/user/.bash_aliases: Read-only file system",
                is_error=True,
            )
        )
        kwargs["stdout"].write(
            _claude_assistant([{"type": "text", "text": RUNTIME_PROBE_MARKER}])
        )
        kwargs["stdout"].flush()
        return OwnedProcessOutcome(returncode=0)

    monkeypatch.setattr("aios_bench.runtime_readiness.run_owned", fake_run_owned)

    result = probe_runtime_readiness(runner)

    assert result.ready is False
    assert result.kind == "tool_probe_failed"


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
