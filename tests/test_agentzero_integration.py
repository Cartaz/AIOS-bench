from __future__ import annotations

import json
from pathlib import Path

import pytest

from aios_bench.adapters import AgentZeroAdapter
from aios_bench.agentzero_client import _validate_profile, normalize_log_items, run
from aios_bench.manifest import build_run_manifest
from aios_bench.telemetry import parse_output


def _agentzero_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_API_KEY", "secret-key")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_URL", "http://127.0.0.1:50001")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROJECT", "aios-bench")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROFILE", "developer")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_ISOLATED_PROJECT", "1")
    monkeypatch.setenv("AIOS_BENCH_REQUESTED_MODEL", "Ornith")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_RESOLVED_MODEL", "Ornith")


def test_agentzero_log_projection_is_structured_and_private() -> None:
    events = normalize_log_items([
        {
            "type": "tool",
            "id": "tool-1",
            "heading": "icon://construction Agent 0: Using tool 'browser:open'",
            "content": "TOP SECRET TOOL RESULT",
            "kvps": {"url": "https://secret.example/private"},
        },
        {
            "type": "subagent",
            "id": "sub-1",
            "heading": "icon://communication Agent 0: Calling Subordinate Agent",
            "content": "TOP SECRET SUBAGENT RESULT",
            "kvps": {"message": "TOP SECRET SUBAGENT PROMPT"},
        },
        {"type": "error", "id": "err-1", "content": "private stack trace"},
        {"type": "response", "id": "resp-1", "content": "private final answer"},
    ])

    kinds = [event["type"] for event in events]
    assert kinds.count("tool_call") == 2
    assert kinds.count("tool_result") == 2
    assert kinds.count("subagent_start") == 1
    assert kinds.count("subagent_end") == 1
    assert kinds.count("error") == 1
    assert kinds.count("assistant") == 1
    assert events[0]["tool"] == "browser"
    assert all(event.get("inferred") is False for event in events)

    serialized = json.dumps(events)
    assert "TOP SECRET" not in serialized
    assert "secret.example" not in serialized
    assert "private stack trace" not in serialized
    assert "private final answer" not in serialized


def test_agentzero_project_and_model_guards_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIOS_BENCH_AGENTZERO_PROJECT", raising=False)
    monkeypatch.delenv("AIOS_BENCH_AGENTZERO_ISOLATED_PROJECT", raising=False)
    with pytest.raises(RuntimeError, match="PROJECT is required"):
        _validate_profile()

    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROJECT", "aios-bench")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_ISOLATED_PROJECT", "0")
    with pytest.raises(RuntimeError, match="ISOLATED_PROJECT=1"):
        _validate_profile()

    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_ISOLATED_PROJECT", "1")
    monkeypatch.setenv("AIOS_BENCH_REQUESTED_MODEL", "Ornith")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_RESOLVED_MODEL", "OtherModel")
    with pytest.raises(RuntimeError, match="does not match"):
        _validate_profile()


def test_agentzero_adapter_declares_observable_capabilities_and_remote_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _agentzero_env(monkeypatch)
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROVIDER", "openai")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_MODEL_ENDPOINT", "http://10.0.0.2:8080/v1")

    adapter = AgentZeroAdapter()
    invocation = adapter.build("do work", tmp_path, "Ornith")

    assert adapter.supports({"browser", "structured_subagent_events", "tool_events"})
    assert "memory" not in adapter.capabilities
    assert invocation.resolved_model == "Ornith"
    assert invocation.model_resolution == "operator_declared_remote"
    assert invocation.provider == "openai"
    assert invocation.endpoint == "http://10.0.0.2:8080/v1"
    assert invocation.configuration["service_endpoint"] == "http://127.0.0.1:50001"
    assert invocation.configuration["fresh_context_per_task"] is True
    assert invocation.configuration["isolated_project_attestation"] is True


def test_agentzero_manifest_keeps_service_endpoint_out_of_model_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _agentzero_env(monkeypatch)
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROVIDER", "openai")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_MODEL_ENDPOINT", "http://10.0.0.2:8080/v1")
    monkeypatch.setenv("AIOS_BENCH_MODEL_DIGEST", "sha256:abc123")
    monkeypatch.setenv("AIOS_BENCH_INFERENCE_CONFIG", '{"reasoning":"off","ctx":98304}')

    adapter = AgentZeroAdapter()
    invocation = adapter.build("do work", tmp_path, "Ornith")
    manifest = build_run_manifest(adapter, invocation, probe_version=False)

    assert manifest["model"]["resolved"] == "Ornith"
    assert manifest["model"]["resolution"] == "operator_declared_remote"
    assert manifest["model"]["endpoint"] == "http://10.0.0.2:8080/v1"
    assert manifest["model"]["strictly_comparable"] is True
    assert manifest["configuration"]["service_endpoint"] == "http://127.0.0.1:50001"


def test_agentzero_run_uses_fresh_context_structured_log_and_cleanup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _agentzero_env(monkeypatch)
    calls: list[tuple[str, dict]] = []

    def fake_request(path: str, payload: dict) -> dict:
        calls.append((path, payload))
        if path == "/api_message":
            return {"context_id": "ctx-new", "response": "MODEL SECRET ANSWER"}
        if path == "/api_log_get":
            return {
                "context_id": "ctx-new",
                "log": {
                    "items": [
                        {
                            "type": "subagent",
                            "id": "sub-1",
                            "heading": "Agent 0: Calling Subordinate Agent",
                            "content": "PRIVATE CHILD OUTPUT",
                            "kvps": {"message": "PRIVATE CHILD PROMPT"},
                        },
                        {
                            "type": "tool",
                            "id": "tool-1",
                            "heading": "Agent 0: Using tool 'browser:open'",
                            "content": "PRIVATE TOOL OUTPUT",
                        },
                        {"type": "response", "id": "r-1", "content": "PRIVATE FINAL"},
                    ]
                },
            }
        if path == "/api_terminate_chat":
            return {"success": True, "context_id": "ctx-new"}
        raise AssertionError(path)

    monkeypatch.setattr("aios_bench.agentzero_client._request_json", fake_request)
    assert run("benchmark prompt") == 0

    captured = capsys.readouterr()
    rows = [json.loads(line) for line in captured.out.splitlines() if line.strip()]
    kinds = [row["type"] for row in rows]
    assert "subagent_start" in kinds
    assert "subagent_end" in kinds
    assert "tool_call" in kinds
    assert "assistant" in kinds
    assert "MODEL SECRET ANSWER" not in captured.out
    assert "PRIVATE" not in captured.out

    assert calls[0][0] == "/api_message"
    assert "context_id" not in calls[0][1]
    assert calls[0][1]["project_name"] == "aios-bench"
    assert calls[0][1]["agent_profile"] == "developer"
    assert calls[1] == ("/api_log_get", {"context_id": "ctx-new", "length": 10000})
    assert calls[-1] == ("/api_terminate_chat", {"context_id": "ctx-new"})


def test_agentzero_jsonl_counts_as_non_inferred_delegation() -> None:
    raw = "\n".join(
        json.dumps(event)
        for event in normalize_log_items([
            {"type": "subagent", "id": "a"},
            {"type": "subagent", "id": "b"},
        ])
    )
    events = [event.to_dict() for event in parse_output(raw, source="agentzero")]
    starts = [event for event in events if event["type"] == "subagent_start"]
    assert len(starts) == 2
    assert all(not (event.get("data") or {}).get("inferred", False) for event in starts)
