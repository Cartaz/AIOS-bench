from pathlib import Path

from aios_bench.adapters import HermesAdapter
from aios_bench.hermes_telemetry import parse_hermes_usage_report
from aios_bench.models import Trajectory
from aios_bench.task_execution import _parse_harness_output


def test_hermes_adapter_pins_isolated_oneshot_tool_surface(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AIOS_BENCH_HERMES_PROVIDER", "openai")
    invocation = HermesAdapter().build("private benchmark prompt", tmp_path, "local/model")

    assert invocation.command[:2] == ["hermes", "--ignore-rules"]
    assert "--toolsets" in invocation.command
    toolsets = invocation.command[invocation.command.index("--toolsets") + 1].split(",")
    assert toolsets == [
        "terminal", "file", "web", "browser", "skills", "todo",
        "code_execution", "delegation",
    ]
    assert "memory" not in toolsets
    assert "session_search" not in toolsets
    assert invocation.command[-4:] == [
        "--model", "local/model", "-z", "private benchmark prompt",
    ]
    assert invocation.provider == "openai"
    assert invocation.requested_model == "local/model"
    assert invocation.resolved_model == "local/model"
    assert invocation.configuration["native_memory_tool"] is False
    assert invocation.configuration["session_search_tool"] is False
    assert invocation.configuration["structured_subagent_events"] is False

    adapter = HermesAdapter()
    assert adapter.assess_capabilities("browser").is_supported
    assert not adapter.assess_capabilities("subagents").is_supported
    assert adapter.assess_capabilities("subagents").missing == frozenset({"structured_subagent_events"})


def test_hermes_usage_report_normalizes_accounting_without_content():
    events = parse_hermes_usage_report(
        '{'
        '"input_tokens":100,"output_tokens":20,"reasoning_tokens":5,"total_tokens":125,'
        '"api_calls":3,"model":"local/model","provider":"openai",'
        '"session_id":"sess-1","completed":true,"failed":false,'
        '"estimated_cost_usd":0.01'
        '}'
    )
    assert [event.type for event in events] == ["session_start", "session_end"]
    end = events[-1]
    assert end.data["model"] == "local/model"
    assert end.data["provider"] == "openai"
    assert end.data["api_calls"] == 3
    assert end.data["usage"] == {
        "input": 100,
        "output": 20,
        "reasoning": 5,
        "total": 125,
    }

    trajectory = Trajectory(agent="hermes", task_id="task")
    trajectory.apply_events([event.to_dict() for event in events])
    assert trajectory.input_tokens == 100
    assert trajectory.output_tokens == 20
    assert trajectory.tool_calls == 0


def test_hermes_failed_usage_report_emits_structured_error_without_failure_text():
    events = parse_hermes_usage_report(
        '{"model":"m","provider":"p","completed":false,"failed":true,'
        '"failure":"private provider traceback"}'
    )
    assert [event.type for event in events] == ["session_start", "error", "session_end"]
    encoded = str([event.to_dict() for event in events])
    assert "private provider traceback" not in encoded


def test_hermes_final_answer_cannot_manufacture_tool_or_subagent_events():
    parsed = _parse_harness_output(
        "I used delegate_task and spawned a subagent. tool call: terminal",
        "",
        "hermes",
        hermes_usage='{"completed":true,"failed":false,"total_tokens":10}',
    )
    kinds = [event["type"] for event in parsed]
    assert "tool_call" not in kinds
    assert "subagent_start" not in kinds
    assert kinds == ["session_start", "session_end"]


def test_hermes_malformed_usage_report_is_ignored():
    assert parse_hermes_usage_report("not json") == []
