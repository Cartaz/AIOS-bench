from aios_bench.models import Trajectory
from aios_bench.telemetry import (
    parse_jsonl,
    parse_opencode_jsonl,
    parse_output,
    parse_pi_rpc,
    parse_text,
)


def test_text_parser_normalizes_common_events():
    events = parse_text("tool call: terminal\nMemory read: preferences\nRetrying after error\n", source="hermes")
    kinds = [event.type for event in events]
    assert "tool_call" in kinds
    assert "memory_read" in kinds
    assert "error" in kinds
    assert "retry" in kinds


def test_jsonl_parser_normalizes_structured_events():
    events = parse_jsonl('{"type":"tool_call","name":"terminal"}\n{"type":"memory_write"}\n', source="pi")
    assert [event.type for event in events] == ["tool_call", "memory_write"]


def test_output_parser_falls_back_to_stderr():
    events = parse_output("", "Traceback: failure\nRetrying\n", source="opencode")
    assert any(event.type == "error" for event in events)
    assert any(event.type == "retry" for event in events)


def test_structured_payloads_drop_prompts_and_bulk_output():
    events = parse_jsonl(
        '{"type":"tool_call","name":"terminal","prompt":"secret","output":"bulk"}\n',
        source="agent",
    )
    encoded = str(events[0].data)
    assert "secret" not in encoded
    assert "bulk" not in encoded
    assert "terminal" in encoded


def test_refusal_is_not_inferred_from_plain_text():
    events = parse_text("I refuse to continue", source="agent")
    assert not any(event.type == "refusal" for event in events)


def test_structured_json_refusal_is_normalized():
    events = parse_jsonl('{"type":"refusal","reason":"safety"}\n', source="agent")
    assert [event.type for event in events] == ["refusal"]


def test_pi_stop_reason_refusal_is_normalized():
    payload = (
        '{"type":"message_end","message":{"role":"assistant","content":[],"stopReason":"refusal"}}\n'
    )
    events = parse_pi_rpc(payload)
    assert any(event.type == "assistant_message" for event in events)
    assert any(event.type == "refusal" for event in events)


def test_opencode_parser_normalizes_tools_subagents_and_cumulative_usage():
    payload = "\n".join([
        '{"type":"step_start","sessionID":"ses_1","part":{"id":"p1","sessionID":"ses_1","type":"step-start"}}',
        '{"type":"tool_use","sessionID":"ses_1","part":{"id":"p2","sessionID":"ses_1","type":"tool","callID":"call_read","tool":"read","state":{"status":"completed","input":{"filePath":"private.txt"},"output":"bulk secret output"}}}',
        '{"type":"step_finish","sessionID":"ses_1","part":{"id":"p3","sessionID":"ses_1","type":"step-finish","reason":"tool-calls","tokens":{"input":100,"output":20,"reasoning":5,"cache":{"read":50,"write":0}}}}',
        '{"type":"tool_use","sessionID":"ses_1","part":{"id":"p4","sessionID":"ses_1","type":"tool","callID":"call_task","tool":"task","state":{"status":"running","input":{"description":"research","prompt":"private delegated prompt","subagent_type":"general"}}}}',
        '{"type":"tool_use","sessionID":"ses_1","part":{"id":"p4","sessionID":"ses_1","type":"tool","callID":"call_task","tool":"task","state":{"status":"completed","input":{"description":"research","prompt":"private delegated prompt","subagent_type":"general"},"output":"bulk child output"}}}',
        '{"type":"step_finish","sessionID":"ses_1","part":{"id":"p5","sessionID":"ses_1","type":"step-finish","reason":"stop","tokens":{"input":50,"output":10,"reasoning":3}}}',
    ])

    events = parse_opencode_jsonl(payload)
    kinds = [event.type for event in events]
    assert kinds.count("session_start") == 1
    assert kinds.count("session_end") == 1
    assert kinds.count("tool_call") == 2
    assert kinds.count("tool_result") == 2
    assert kinds.count("file_read") == 1
    assert kinds.count("subagent_start") == 1
    assert kinds.count("subagent_end") == 1

    subagent = next(event for event in events if event.type == "subagent_start")
    assert subagent.data["call_id"] == "call_task"
    assert subagent.data["inferred"] is False

    trajectory = Trajectory(agent="opencode", task_id="task")
    trajectory.apply_events([event.to_dict() for event in events])
    assert trajectory.input_tokens == 150
    assert trajectory.output_tokens == 30
    assert trajectory.tool_calls == 2
    assert trajectory.files_read == 1

    encoded = str([event.to_dict() for event in events])
    assert "private.txt" not in encoded
    assert "private delegated prompt" not in encoded
    assert "bulk secret output" not in encoded
    assert "bulk child output" not in encoded


def test_opencode_output_dispatches_to_dedicated_parser():
    payload = (
        '{"type":"tool_use","sessionID":"ses_1","part":{"id":"p1","callID":"call_task",'
        '"tool":"task","state":{"status":"completed"}}}\n'
    )
    events = parse_output(payload, source="opencode")
    assert any(event.type == "subagent_start" and event.data.get("inferred") is False for event in events)
    assert any(event.type == "subagent_end" and event.data.get("inferred") is False for event in events)
