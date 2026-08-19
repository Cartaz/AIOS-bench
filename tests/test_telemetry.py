from aios_bench.telemetry import parse_jsonl, parse_output, parse_text


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
