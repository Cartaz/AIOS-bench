from __future__ import annotations

import json
from pathlib import Path

import pytest

from aios_bench.adapters import AgentZeroAdapter
from aios_bench.agentzero_client import _validate_profile, normalize_log_items, run
from aios_bench.agentzero_workspace import (
    EphemeralAgentZeroProject,
    validate_template_project,
)
from aios_bench.bubblewrap import BubblewrapCapability
from aios_bench.manifest import build_run_manifest
from aios_bench.sandbox import workspace_sandbox
from aios_bench.telemetry import parse_output


def _make_template(root: Path, name: str = "aios-bench") -> Path:
    template = root / name
    meta = template / ".a0proj"
    meta.mkdir(parents=True)
    (meta / "project.json").write_text(
        json.dumps({
            "title": "AIOS-bench",
            "description": "",
            "instructions": "",
            "include_agents_md": False,
            "git_url": "",
        }),
        encoding="utf-8",
    )
    (meta / "mcp_servers.json").write_text('{"mcpServers":{}}', encoding="utf-8")
    return template


def _agentzero_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, Path]:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    _make_template(projects_root)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_API_KEY", "secret-key")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_URL", "http://127.0.0.1:50001")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROJECT", "aios-bench")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROFILE", "developer")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_ISOLATED_SERVICE", "1")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROJECT_MEMORY_ISOLATION", "1")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_REVISION", "b22a144bf59f15b1516084c9e7b88133ba92c8a9")
    monkeypatch.setenv("AIOS_BENCH_WORKSPACE", str(workspace))
    monkeypatch.setenv("AIOS_BENCH_REQUESTED_MODEL", "Ornith")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_RESOLVED_MODEL", "Ornith")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_UTILITY_MODEL", "Ornith")
    return projects_root, workspace


def test_agentzero_log_projection_is_structured_private_and_fail_closed() -> None:
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
        {
            "type": "subagent",
            "id": "sub-incomplete",
            "heading": "icon://communication Agent 0: Calling Subordinate Agent",
            "content": "",
        },
        {"type": "error", "id": "err-1", "content": "private stack trace"},
        {"type": "response", "id": "resp-1", "content": "private final answer"},
    ])

    kinds = [event["type"] for event in events]
    assert kinds.count("tool_call") == 3
    assert kinds.count("tool_result") == 2
    assert kinds.count("subagent_start") == 2
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


def test_agentzero_profile_guards_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root, workspace = _agentzero_env(monkeypatch, tmp_path)

    monkeypatch.delenv("AIOS_BENCH_AGENTZERO_PROJECT", raising=False)
    with pytest.raises(RuntimeError, match="PROJECT is required"):
        _validate_profile()

    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROJECT", "aios-bench")
    monkeypatch.delenv("AIOS_BENCH_AGENTZERO_PROJECTS_ROOT", raising=False)
    with pytest.raises(RuntimeError, match="PROJECTS_ROOT is required"):
        _validate_profile()

    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setenv("AIOS_BENCH_WORKSPACE", str(workspace))
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_ISOLATED_SERVICE", "0")
    with pytest.raises(RuntimeError, match="ISOLATED_SERVICE=1"):
        _validate_profile()

    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_ISOLATED_SERVICE", "1")
    monkeypatch.delenv("AIOS_BENCH_AGENTZERO_PROJECT_MEMORY_ISOLATION", raising=False)
    with pytest.raises(RuntimeError, match="PROJECT_MEMORY_ISOLATION=1"):
        _validate_profile()

    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROJECT_MEMORY_ISOLATION", "1")
    monkeypatch.delenv("AIOS_BENCH_AGENTZERO_REVISION", raising=False)
    with pytest.raises(RuntimeError, match="AGENTZERO_REVISION is required"):
        _validate_profile()

    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_REVISION", "agentzero-revision")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_RESOLVED_MODEL", "OtherModel")
    with pytest.raises(RuntimeError, match="resolved-model declaration does not match"):
        _validate_profile()

    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_RESOLVED_MODEL", "Ornith")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_UTILITY_MODEL", "OtherModel")
    with pytest.raises(RuntimeError, match="utility-model declaration does not match"):
        _validate_profile()


def test_agentzero_template_validation_and_digest(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    template = _make_template(projects_root)

    validated, digest = validate_template_project(projects_root, "aios-bench")
    assert validated == template.resolve()
    assert digest.startswith("sha256:")

    (template / "personal.txt").write_text("should not leak", encoding="utf-8")
    with pytest.raises(RuntimeError, match="metadata only"):
        validate_template_project(projects_root, "aios-bench")


def test_agentzero_template_rejects_ambient_customization(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    template = _make_template(projects_root)
    instructions = template / ".a0proj" / "instructions"
    instructions.mkdir()
    (instructions / "personal.md").write_text("personal instruction", encoding="utf-8")
    with pytest.raises(RuntimeError, match="custom instructions"):
        validate_template_project(projects_root, "aios-bench")


def test_ephemeral_project_round_trip_excludes_agentzero_metadata(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    _make_template(projects_root)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "input.txt").write_text("fixture", encoding="utf-8")
    nested = workspace / "data"
    nested.mkdir()
    (nested / "rows.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    bridge = EphemeralAgentZeroProject(workspace, projects_root, "aios-bench")
    name = bridge.prepare()
    assert name != "aios-bench"
    assert bridge.project_path is not None
    assert (bridge.project_path / "input.txt").read_text(encoding="utf-8") == "fixture"
    assert (bridge.project_path / ".a0proj" / "project.json").is_file()

    (bridge.project_path / "input.txt").unlink()
    (bridge.project_path / "result.txt").write_text("done", encoding="utf-8")
    (bridge.project_path / ".a0proj" / "runtime-private.txt").write_text(
        "not a benchmark artifact", encoding="utf-8"
    )
    bridge.sync_back()

    assert not (workspace / "input.txt").exists()
    assert (workspace / "result.txt").read_text(encoding="utf-8") == "done"
    assert not (workspace / ".a0proj").exists()
    bridge.cleanup()
    assert not (projects_root / name).exists()
    assert (projects_root / "aios-bench").is_dir()


def test_ephemeral_project_rejects_remote_symlink_before_touching_workspace(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    _make_template(projects_root)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    original = workspace / "keep.txt"
    original.write_text("keep", encoding="utf-8")

    bridge = EphemeralAgentZeroProject(workspace, projects_root, "aios-bench")
    bridge.prepare()
    assert bridge.project_path is not None
    (bridge.project_path / "escape").symlink_to("/etc/passwd")
    with pytest.raises(RuntimeError, match="symlink"):
        bridge.sync_back()
    assert original.read_text(encoding="utf-8") == "keep"
    bridge.cleanup()


def test_agentzero_adapter_declares_observable_capabilities_and_remote_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root, workspace = _agentzero_env(monkeypatch, tmp_path)
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROVIDER", "openai")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_MODEL_ENDPOINT", "http://10.0.0.2:8080/v1")

    adapter = AgentZeroAdapter()
    invocation = adapter.build("do work", workspace, "Ornith")

    assert adapter.supports({"browser", "structured_subagent_events", "tool_events"})
    assert "memory" not in adapter.capabilities
    assert invocation.resolved_model == "Ornith"
    assert invocation.model_resolution == "operator_declared_remote"
    assert invocation.provider == "openai"
    assert invocation.endpoint == "http://10.0.0.2:8080/v1"
    assert invocation.configuration["service_endpoint"] == "http://127.0.0.1:50001"
    assert invocation.configuration["service_revision"] == "b22a144bf59f15b1516084c9e7b88133ba92c8a9"
    assert invocation.configuration["service_revision_resolution"] == "operator_declared_remote"
    assert invocation.configuration["fresh_context_per_task"] is True
    assert invocation.configuration["ephemeral_physical_project_per_task"] is True
    assert invocation.configuration["isolated_service_attestation"] is True
    assert invocation.configuration["project_memory_isolation_attestation"] is True
    assert invocation.configuration["main_model_attestation"] == "Ornith"
    assert invocation.configuration["utility_model_attestation"] == "Ornith"
    assert invocation.configuration["project_template_digest"].startswith("sha256:")
    assert invocation.configuration["projects_root_configured"] is True
    assert str(projects_root) not in json.dumps(invocation.configuration)


def test_agentzero_manifest_keeps_service_endpoint_out_of_model_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root, workspace = _agentzero_env(monkeypatch, tmp_path)
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROVIDER", "openai")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_MODEL_ENDPOINT", "http://10.0.0.2:8080/v1")
    monkeypatch.setenv("AIOS_BENCH_MODEL_DIGEST", "sha256:abc123")
    monkeypatch.setenv("AIOS_BENCH_INFERENCE_CONFIG", '{"reasoning":"off","ctx":98304}')

    adapter = AgentZeroAdapter()
    invocation = adapter.build("do work", workspace, "Ornith")
    manifest = build_run_manifest(adapter, invocation, probe_version=False)

    assert manifest["model"]["resolved"] == "Ornith"
    assert manifest["model"]["resolution"] == "operator_declared_remote"
    assert manifest["model"]["endpoint"] == "http://10.0.0.2:8080/v1"
    assert manifest["model"]["strictly_comparable"] is True
    assert manifest["configuration"]["service_endpoint"] == "http://127.0.0.1:50001"
    assert manifest["configuration"]["service_revision"] == "b22a144bf59f15b1516084c9e7b88133ba92c8a9"
    assert manifest["configuration"]["utility_model_attestation"] == "Ornith"
    assert str(projects_root) not in json.dumps(manifest["configuration"])


def test_agentzero_run_uses_ephemeral_project_log_sync_and_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    projects_root, workspace = _agentzero_env(monkeypatch, tmp_path)
    (workspace / "fixture.txt").write_text("input", encoding="utf-8")
    calls: list[tuple[str, dict]] = []
    used_project: str | None = None

    def fake_request(path: str, payload: dict) -> dict:
        nonlocal used_project
        calls.append((path, payload))
        if path == "/api_message":
            used_project = str(payload["project_name"])
            remote = projects_root / used_project
            assert used_project != "aios-bench"
            assert (remote / "fixture.txt").read_text(encoding="utf-8") == "input"
            (remote / "fixture.txt").unlink()
            (remote / "result.txt").write_text("done", encoding="utf-8")
            return {"context_id": "ctx-new", "response": "MODEL SECRET ANSWER"}
        if path == "/api_log_get":
            return {
                "context_id": "ctx-new",
                "log": {"items": [
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
                ]},
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
    assert calls[0][1]["agent_profile"] == "developer"
    assert calls[1] == ("/api_log_get", {"context_id": "ctx-new", "length": 10000})
    assert calls[2] == ("/api_terminate_chat", {"context_id": "ctx-new"})
    assert (workspace / "result.txt").read_text(encoding="utf-8") == "done"
    assert not (workspace / "fixture.txt").exists()
    assert used_project is not None and not (projects_root / used_project).exists()
    assert (projects_root / "aios-bench").is_dir()


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


def test_agentzero_sandbox_adds_only_shared_projects_root_write_bridge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda _: "/usr/bin/bwrap")
    monkeypatch.setattr(
        "aios_bench.sandbox.probe_bubblewrap",
        lambda executable: BubblewrapCapability(True),
    )

    plan = workspace_sandbox("agentzero", workspace)
    prefix = list(plan.command_prefix)
    bridge = str(projects_root.resolve())
    assert "agentzero_project_bridge" in plan.strategy
    pairs = list(zip(prefix, prefix[1:]))
    assert ("--bind", bridge) in pairs
    assert plan.write_confined is True
