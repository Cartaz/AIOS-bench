from pathlib import Path

from aios_bench.adapters import LettaAdapter
from aios_bench.letta_telemetry import parse_letta_stream_json
from aios_bench.models import Trajectory


def test_letta_adapter_uses_isolated_stream_json_profile(monkeypatch, tmp_path: Path):
    # A developer may have used the old persistent-agent profile locally. The
    # benchmark profile must not inherit it.
    monkeypatch.setenv("AIOS_BENCH_LETTA_AGENT", "agent-personal")
    invocation = LettaAdapter().build("private benchmark prompt", tmp_path, "local/model")

    assert invocation.command == [
        "letta", "-p",
        "--ephemeral",
        "--output-format", "stream-json",
        "--yolo",
        "--no-mods",
        "--skill-sources", "bundled",
        "--model", "local/model",
        "private benchmark prompt",
    ]
    assert "--agent" not in invocation.command
    assert invocation.requested_model == "local/model"
    assert invocation.resolved_model == "local/model"
    assert invocation.configuration["ephemeral"] is True
    assert invocation.configuration["output_format"] == "stream-json"
    assert invocation.configuration["mods"] == "disabled"
    assert invocation.configuration["skill_sources"] == ["bundled"]
    assert LettaAdapter().assess_capabilities("subagents").is_supported
    assert not LettaAdapter().assess_capabilities("browser").is_supported


def test_letta_stream_json_normalizes_tools_usage_and_subagents_without_payload_leakage():
    payload = "\n".join([
        '{"type":"system","subtype":"init","session_id":"sess-1",'
        '"conversation_id":"conv-1","model":"local/model","permission_mode":"unrestricted",'
        '"tools":["Bash","Agent"]}',
        '{"type":"message","message_type":"tool_call_message","session_id":"sess-1",'
        '"tool_call":{"name":"Bash","tool_call_id":"call-shell",'
        '"arguments":"{\\"command\\":\\"cat secret.txt\\"}"}}',
        '{"type":"message","message_type":"tool_return_message","session_id":"sess-1",'
        '"tool_call_id":"call-shell","status":"success","tool_return":"secret tool output",'
        '"stdout":"private stdout","stderr":"private stderr"}',
        '{"type":"message","message_type":"tool_call_message","session_id":"sess-1",'
        '"tool_call":{"name":"Agent","tool_call_id":"call-agent",'
        '"arguments":"{\\"prompt\\":\\"private child task\\"}"}}',
        '{"type":"message","message_type":"tool_return_message","session_id":"sess-1",'
        '"tool_call_id":"call-agent","status":"success","tool_return":"private subagent result"}',
        '{"type":"result","subtype":"success","session_id":"sess-1",'
        '"conversation_id":"conv-1","result":"private final answer",'
        '"usage":{"input_tokens":100,"output_tokens":20,"reasoning_tokens":5,"total_tokens":125}}',
    ])

    events = parse_letta_stream_json(payload)
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
        "tool": "Agent", "call_id": "call-agent", "inferred": False,
    }
    assert end.data["tool"] == "Agent"
    assert end.data["call_id"] == "call-agent"
    assert end.data["inferred"] is False

    session_end = next(event for event in events if event.type == "session_end")
    assert session_end.data["usage"] == {
        "input": 100,
        "output": 20,
        "reasoning": 5,
        "total": 125,
    }

    trajectory = Trajectory(agent="letta", task_id="task")
    trajectory.apply_events([event.to_dict() for event in events])
    assert trajectory.input_tokens == 100
    assert trajectory.output_tokens == 20
    assert trajectory.tool_calls == 2

    encoded = str([event.to_dict() for event in events])
    assert "cat secret.txt" not in encoded
    assert "secret tool output" not in encoded
    assert "private stdout" not in encoded
    assert "private stderr" not in encoded
    assert "private child task" not in encoded
    assert "private subagent result" not in encoded
    assert "private final answer" not in encoded


def test_letta_subagent_requires_structured_tool_call():
    events = parse_letta_stream_json(
        'I delegated this to a subagent\n'
        '{"type":"message","message_type":"assistant_message","session_id":"sess-1",'
        '"content":"I used Agent and Task to delegate work"}\n'
        '{"type":"result","subtype":"success","session_id":"sess-1",'
        '"conversation_id":"conv-1","usage":null}\n'
    )
    assert not any(event.type == "subagent_start" for event in events)


def test_letta_incomplete_stream_does_not_invent_session_end():
    events = parse_letta_stream_json(
        '{"type":"system","subtype":"init","session_id":"sess-1",'
        '"conversation_id":"conv-1","model":"local/model","tools":[]}\n'
        '{"type":"message","message_type":"assistant_message","session_id":"sess-1",'
        '"content":"partial response before timeout"}\n'
    )
    assert any(event.type == "session_start" for event in events)
    assert not any(event.type == "session_end" for event in events)


def test_letta_structured_error_retry_and_refusal_are_reliable():
    events = parse_letta_stream_json(
        '{"type":"retry","session_id":"sess-1","reason":"llm_api_error",'
        '"attempt":1,"message":"private retry detail"}\n'
        '{"type":"error","session_id":"sess-1","stop_reason":"content_filter",'
        '"message":"private provider error"}\n'
        '{"type":"result","subtype":"error","session_id":"sess-1",'
        '"conversation_id":"conv-1","result":"private result",'
        '"stop_reason":"content_filter","usage":null}\n'
    )
    kinds = [event.type for event in events]
    assert kinds.count("retry") == 1
    assert kinds.count("error") == 2
    assert kinds.count("refusal") == 2
    assert kinds.count("session_end") == 1

    encoded = str([event.to_dict() for event in events])
    assert "private retry detail" not in encoded
    assert "private provider error" not in encoded
    assert "private result" not in encoded
