from aios_bench.telemetry import parse_jsonl, parse_output, parse_pi_rpc, parse_text


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
