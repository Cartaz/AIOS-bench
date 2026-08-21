from pathlib import Path

from aios_bench.adapters import GooseAdapter
from aios_bench.goose_telemetry import parse_goose_stream_json
from aios_bench.models import Trajectory


def test_goose_adapter_uses_reproducible_stream_json_mode(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AIOS_BENCH_GOOSE_PROVIDER", "openai")
    invocation = GooseAdapter().build("private benchmark prompt", tmp_path, "local/model")

    assert invocation.command == [
        "goose", "run", "--no-session", "--quiet",
        "--output-format", "stream-json", "--with-builtin", "developer",
        "--provider", "openai", "--model", "local/model",
        "-t", "private benchmark prompt",
    ]
    assert invocation.configuration["output_format"] == "stream-json"
    assert invocation.configuration["builtin_extensions"] == ["developer"]
    assert invocation.configuration["summon_delegate"] == "default_enabled_platform_extension"
    assert GooseAdapter().assess_capabilities("subagents").is_supported
    assert not GooseAdapter().assess_capabilities("browser").is_supported


def test_goose_stream_json_normalizes_tools_and_delegate_without_payload_leakage():
    payload = "\n".join([
        '{"type":"message","message":{"role":"assistant","content":['
        '{"type":"text","text":"private assistant prose"},'
        '{"type":"toolRequest","id":"call_shell","toolCall":{"status":"success","value":'
        '{"name":"shell","arguments":{"command":"cat secret.txt"}}}},'
        '{"type":"toolRequest","id":"call_delegate","toolCall":{"status":"success","value":'
        '{"name":"delegate","arguments":{"instructions":"private child task","async":false}}}}]}}',
        '{"type":"message","message":{"role":"user","content":['
        '{"type":"toolResponse","id":"call_shell","toolResult":{"status":"success",'
        '"value":{"content":[{"type":"text","text":"secret tool output"}]}}},'
        '{"type":"toolResponse","id":"call_delegate","toolResult":{"status":"success",'
        '"value":{"content":[{"type":"text","text":"private subagent result"}]}}}]}}',
        '{"type":"complete","total_tokens":4321}',
    ])

    events = parse_goose_stream_json(payload)
    kinds = [event.type for event in events]
    assert kinds.count("session_start") == 1
    assert kinds.count("session_end") == 1
    assert kinds.count("tool_call") == 2
    assert kinds.count("tool_result") == 2
    assert kinds.count("terminal") == 1
    assert kinds.count("subagent_start") == 1
    assert kinds.count("subagent_end") == 1

    start = next(event for event in events if event.type == "subagent_start")
    end = next(event for event in events if event.type == "subagent_end")
    assert start.data == {
        "tool": "delegate", "call_id": "call_delegate", "inferred": False,
    }
    assert end.data["call_id"] == "call_delegate"
    assert end.data["inferred"] is False

    session_end = next(event for event in events if event.type == "session_end")
    assert session_end.data["usage"]["total"] == 4321
    assert session_end.data["usage"]["input"] == 0
    assert session_end.data["usage"]["output"] == 0

    encoded = str([event.to_dict() for event in events])
    assert "private assistant prose" not in encoded
    assert "cat secret.txt" not in encoded
    assert "private child task" not in encoded
    assert "secret tool output" not in encoded
    assert "private subagent result" not in encoded


def test_goose_delegate_requires_structured_tool_request():
    events = parse_goose_stream_json(
        'I delegated this to a subagent\n'
        '{"type":"message","message":{"role":"assistant","content":['
        '{"type":"text","text":"I used delegate and a subagent"}]}}\n'
        '{"type":"complete","total_tokens":10}\n'
    )
    assert not any(event.type == "subagent_start" for event in events)


def test_goose_structured_error_is_reliable_and_total_only_usage_is_not_faked():
    events = parse_goose_stream_json(
        '{"type":"error","error":"provider private detail"}\n'
        '{"type":"complete","total_tokens":99}\n'
    )
    error = next(event for event in events if event.type == "error")
    assert error.data["inferred"] is False
    assert "provider private detail" not in str(error.data)

    trajectory = Trajectory(agent="goose", task_id="task")
    trajectory.apply_events([event.to_dict() for event in events])
    assert trajectory.errors == 1
    assert trajectory.input_tokens == 0
    assert trajectory.output_tokens == 0
