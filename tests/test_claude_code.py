from __future__ import annotations

import json
from pathlib import Path

from aios_bench.adapters import ClaudeCodeAdapter
from aios_bench.manifest import build_run_manifest
from aios_bench.models import Trajectory
from aios_bench.telemetry import parse_claude_jsonl, parse_output


def test_claude_adapter_isolates_and_pins_local_model(monkeypatch, tmp_path: Path):
    endpoint = "http://user:password@127.0.0.1:8081/v1?token=leak#fragment"
    monkeypatch.setenv("AIOS_BENCH_CLAUDE_BASE_URL", endpoint)
    monkeypatch.setenv("AIOS_BENCH_CLAUDE_API_KEY", "super-secret-value")

    adapter = ClaudeCodeAdapter()
    invocation = adapter.build("private benchmark prompt", tmp_path, "local/model")
    command = invocation.command
    environment = invocation.environment

    assert command[0] == "claude"
    for flag in (
        "--safe-mode",
        "-p",
        "--verbose",
        "--no-session-persistence",
        "--dangerously-skip-permissions",
        "--no-chrome",
        "--strict-mcp-config",
        "--disable-slash-commands",
    ):
        assert flag in command
    assert command[command.index("--output-format") + 1] == "stream-json"
    assert command[command.index("--model") + 1] == "local/model"
    assert command[-1] == "private benchmark prompt"

    assert environment["ANTHROPIC_BASE_URL"] == endpoint
    assert environment["ANTHROPIC_API_KEY"] == "super-secret-value"
    assert environment["CLAUDE_CODE_SKIP_PROMPT_HISTORY"] == "1"
    assert environment["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] == "1"
    assert environment["DISABLE_TELEMETRY"] == "1"
    assert environment["DISABLE_AUTOUPDATER"] == "1"
    assert str(environment["CLAUDE_CONFIG_DIR"]).startswith("/tmp/")

    for key in (
        "ANTHROPIC_MODEL",
        "ANTHROPIC_DEFAULT_FABLE_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "CLAUDE_CODE_SUBAGENT_MODEL",
    ):
        assert environment[key] == "local/model"

    manifest = build_run_manifest(adapter, invocation, probe_version=False)
    encoded = json.dumps(manifest)
    assert "private benchmark prompt" not in encoded
    assert "super-secret-value" not in encoded
    assert "password" not in encoded
    assert "token=leak" not in encoded
    assert manifest["model"]["requested"] == "local/model"
    assert manifest["model"]["resolved"] == "local/model"
    assert manifest["model"]["endpoint"] == "http://127.0.0.1:8081/v1"
    assert manifest["configuration"]["safe_mode"] is True
    assert manifest["configuration"]["api_key_configured"] is True
    assert manifest["configuration"]["default_model_aliases_pinned"] is True
    assert manifest["configuration"]["subagent_model_pinned"] is True


def test_claude_stream_parser_normalizes_tools_subagents_retries_and_usage():
    payload = "\n".join([
        json.dumps({
            "type": "system",
            "subtype": "init",
            "session_id": "ses_1",
            "model": "local/model",
            "tools": ["Read", "Write", "Bash", "Agent"],
            "mcp_servers": [],
            "plugins": [],
        }),
        json.dumps({
            "type": "assistant",
            "session_id": "ses_1",
            "parent_tool_use_id": None,
            "message": {
                "id": "msg_1",
                "role": "assistant",
                "stop_reason": "tool_use",
                "usage": {
                    "input_tokens": 100,
                    "cache_read_input_tokens": 20,
                    "cache_creation_input_tokens": 10,
                    "output_tokens": 12,
                },
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_read",
                        "name": "Read",
                        "input": {"file_path": "private.txt"},
                    },
                    {
                        "type": "tool_use",
                        "id": "tool_agent",
                        "name": "Agent",
                        "input": {"prompt": "private child prompt"},
                    },
                ],
            },
        }),
        json.dumps({
            "type": "user",
            "session_id": "ses_1",
            "parent_tool_use_id": None,
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_read",
                        "content": "secret read output",
                    },
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_agent",
                        "content": "secret child output",
                    },
                ],
            },
        }),
        json.dumps({
            "type": "system",
            "subtype": "api_retry",
            "attempt": 1,
            "max_retries": 10,
            "retry_delay_ms": 250,
            "error_status": 529,
            "error": "overloaded",
            "session_id": "ses_1",
        }),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "session_id": "ses_1",
            "is_error": False,
            "num_turns": 2,
            "stop_reason": "end_turn",
            "terminal_reason": "completed",
            "usage": {
                "input_tokens": 200,
                "cache_creation_input_tokens": 30,
                "cache_read_input_tokens": 50,
                "output_tokens": 40,
            },
            "modelUsage": {"local/model": {"inputTokens": 200}},
            "result": "private final response",
        }),
    ]) + "\n"

    events = parse_claude_jsonl(payload)
    kinds = [event.type for event in events]
    assert kinds.count("session_start") == 1
    assert kinds.count("session_end") == 1
    assert kinds.count("tool_call") == 2
    assert kinds.count("tool_result") == 2
    assert kinds.count("file_read") == 1
    assert kinds.count("subagent_start") == 1
    assert kinds.count("subagent_end") == 1
    assert kinds.count("retry") == 1

    subagent = next(event for event in events if event.type == "subagent_start")
    assert subagent.data["call_id"] == "tool_agent"
    assert subagent.data["inferred"] is False
    session_end = next(event for event in events if event.type == "session_end")
    assert session_end.data["models"] == ["local/model"]
    assert session_end.data["inferred"] is False

    trajectory = Trajectory(agent="claude", task_id="task")
    trajectory.apply_events([event.to_dict() for event in events])
    assert trajectory.input_tokens == 280
    assert trajectory.output_tokens == 40
    assert trajectory.tool_calls == 2
    assert trajectory.files_read == 1
    assert trajectory.retries == 1

    encoded = str([event.to_dict() for event in events])
    assert "private.txt" not in encoded
    assert "private child prompt" not in encoded
    assert "secret read output" not in encoded
    assert "secret child output" not in encoded
    assert "private final response" not in encoded


def test_claude_output_dispatches_to_dedicated_parser():
    payload = "\n".join([
        json.dumps({
            "type": "assistant",
            "session_id": "ses_1",
            "message": {
                "id": "msg_1",
                "content": [
                    {"type": "tool_use", "id": "tool_agent", "name": "Agent", "input": {}},
                ],
            },
        }),
        json.dumps({
            "type": "user",
            "session_id": "ses_1",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "tool_agent", "content": "done"},
                ],
            },
        }),
        json.dumps({"type": "result", "subtype": "success", "session_id": "ses_1", "usage": {}}),
    ]) + "\n"

    events = parse_output(payload, source="claude")
    assert any(event.type == "subagent_start" and event.data.get("inferred") is False for event in events)
    assert any(event.type == "subagent_end" and event.data.get("inferred") is False for event in events)
