from aios_bench.telemetry import parse_jsonl, parse_opencode_jsonl, parse_output, parse_text


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


def test_opencode_parser_normalizes_real_run_event_shapes():
    payload = "\n".join([
        '{"type":"step_start","sessionID":"ses_1","part":{"id":"p1","type":"step-start"}}',
        '{"type":"tool_use","sessionID":"ses_1","part":{"id":"p2","type":"tool","callID":"call_1","tool":"bash","state":{"status":"completed","input":{"command":"echo secret"},"output":"bulk output"}}}',
        '{"type":"step_finish","sessionID":"ses_1","part":{"id":"p3","type":"step-finish","reason":"tool-calls","tokens":{"input":100,"output":10,"reasoning":2}}}',
        '{"type":"text","sessionID":"ses_1","part":{"id":"p4","type":"text","text":"done"}}',
        '{"type":"step_finish","sessionID":"ses_1","part":{"id":"p5","type":"step-finish","reason":"stop","tokens":{"input":120,"output":20,"reasoning":3}}}',
    ])

    events = parse_opencode_jsonl(payload)
    kinds = [event.type for event in events]

    assert kinds.count("session_start") == 1
    assert "tool_call" in kinds
    assert "tool_result" in kinds
    assert "terminal" in kinds
    assert "assistant_message" in kinds
    assert kinds.count("session_end") == 1
    session_end = next(event for event in events if event.type == "session_end")
    assert session_end.data["usage"] == {"input": 120, "output": 20, "reasoning": 3, "total": 143}
    encoded = str([event.data for event in events])
    assert "echo secret" not in encoded
    assert "bulk output" not in encoded


def test_opencode_task_tool_is_not_fake_structured_subagent_telemetry():
    events = parse_opencode_jsonl(
        '{"type":"tool_use","sessionID":"ses_1","part":{"id":"p2","type":"tool","callID":"call_1","tool":"task","state":{"status":"completed"}}}'
    )
    assert any(event.type == "tool_call" for event in events)
    assert not any(event.type == "subagent_start" for event in events)


def test_output_parser_routes_opencode_to_dedicated_parser():
    events = parse_output(
        '{"type":"text","sessionID":"ses_1","part":{"type":"text","text":"hello"}}\n',
        source="opencode",
    )
    assert [event.type for event in events] == ["assistant_message"]


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
