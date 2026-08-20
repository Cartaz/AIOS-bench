from aios_bench.telemetry import parse_pi_rpc


RPC_FIXTURE = """\
{"id":"test-1","type":"response","command":"prompt","success":true}
{"type":"agent_start"}
{"type":"turn_start"}
{"type":"message_start","message":{"role":"user","content":[{"type":"text","text":"Do it"}]}}
{"type":"message_end","message":{"role":"user","content":[{"type":"text","text":"Do it"}]}}
{"type":"message_start","message":{"role":"assistant","content":[],"usage":{"input":0,"output":0,"totalTokens":0}}}
{"type":"message_update","assistantMessageEvent":{"type":"text_delta","contentIndex":0,"delta":"done"},"usage":{"input":0,"output":0,"totalTokens":0}}
{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"done"}],"usage":{"input":1551,"output":7,"reasoning":0,"totalTokens":1558},"stopReason":"stop"}}
{"type":"tool_execution_start","toolName":"bash","toolCallId":"call-1"}
{"type":"tool_execution_end","toolName":"bash","toolCallId":"call-1","isError":false}
{"type":"agent_end","willRetry":false}
{"type":"agent_settled"}
"""


def test_pi_rpc_normalizes_lifecycle_tools_and_usage():
    events = parse_pi_rpc(RPC_FIXTURE)
    kinds = [event.type for event in events]
    assert "session_start" in kinds
    assert "session_end" in kinds
    assert "assistant_message" in kinds
    assert kinds.count("tool_call") == 1
    assert kinds.count("tool_result") == 1

    usage_events = [event for event in events if event.type == "assistant_message" and event.data.get("usage")]
    assert usage_events
    assert max(event.data["usage"]["input"] for event in usage_events) == 1551
    assert max(event.data["usage"]["output"] for event in usage_events) == 7


def test_pi_rpc_ignores_command_ack():
    events = parse_pi_rpc('{"id":"x","type":"response","command":"prompt","success":true}\n')
    assert events == []


def test_pi_rpc_does_not_persist_streaming_deltas():
    events = parse_pi_rpc(
        '{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"secret delta"}}\n'
    )
    assert events == []
