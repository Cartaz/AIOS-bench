from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from aios_bench.adapters import (
    Adapter,
    AgentInvocation,
    AgentZeroAdapter,
    CodexAdapter,
    HermesAdapter,
    LettaAdapter,
    required_capabilities_for,
)
from aios_bench.manifest import build_run_manifest, probe_executable, sanitize_configuration


class StructuredDelegationAdapter(Adapter):
    name = "structured"
    capabilities = frozenset({"structured_subagent_events"})


def test_capability_assessment_separates_native_feature_from_observability():
    native_only = LettaAdapter().assess_capabilities("subagents")
    structured = StructuredDelegationAdapter().assess_capabilities("subagents")

    assert native_only.status == "unsupported"
    assert native_only.missing == frozenset({"structured_subagent_events"})
    assert structured.status == "supported"
    assert structured.to_dict()["missing"] == []


def test_category_and_catalog_tag_requirements_are_composed():
    required = required_capabilities_for("browser", ["grounded", "requires:citations"])

    assert required == frozenset({"browser", "citations"})
    assert HermesAdapter().assess_capabilities("browser").is_supported
    assert not CodexAdapter().assess_capabilities("browser").is_supported
    assert CodexAdapter().assess_capabilities("coding").is_supported


def test_task_explicit_requirements_are_included():
    task = SimpleNamespace(
        category="coding", tags=(), required_capabilities=("terminal", "workspace_write")
    )

    assessment = CodexAdapter().assess_task(task)

    assert assessment.is_supported
    assert assessment.required == frozenset({"terminal", "workspace_write"})


def test_agentzero_manifest_never_serializes_api_key(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_API_KEY", "super-secret-value")
    monkeypatch.setenv(
        "AIOS_BENCH_AGENTZERO_URL",
        "https://user:password@example.test:8443/api?api_key=leak#fragment",
    )
    invocation = AgentZeroAdapter().build("prompt must not be serialized", tmp_path, "requested/model")

    manifest = build_run_manifest(AgentZeroAdapter(), invocation, probe_version=False)
    encoded = json.dumps(manifest)

    assert "super-secret-value" not in encoded
    assert "prompt must not be serialized" not in encoded
    assert "password" not in encoded
    assert "api_key=leak" not in encoded
    assert manifest["model"] == {
        "requested": "requested/model",
        "resolved": None,
        "resolution": "requested_unverified",
        "provider": None,
        "endpoint": "https://example.test:8443/api",
    }
    assert manifest["configuration"]["api_key_configured"] is True


def test_manifest_records_explicitly_pinned_model_and_safe_configuration(tmp_path: Path):
    adapter = CodexAdapter()
    invocation = adapter.build("private prompt", tmp_path, "openai/gpt-test")
    manifest = build_run_manifest(
        adapter,
        invocation,
        configuration={"temperature": 0, "access_token": "do-not-store"},
        probe_version=False,
    )

    assert manifest["model"]["requested"] == "openai/gpt-test"
    assert manifest["model"]["resolved"] == "openai/gpt-test"
    assert manifest["model"]["resolution"] == "adapter_pinned"
    assert manifest["configuration"]["sandbox"] == "workspace-write"
    assert manifest["configuration"]["access_token"] == "[redacted]"


def test_manifest_accepts_harness_observed_model(tmp_path: Path):
    adapter = LettaAdapter()
    invocation = adapter.build("prompt", tmp_path, "requested-alias")

    manifest = build_run_manifest(
        adapter,
        invocation,
        resolved_model="provider/canonical-model",
        provider="local",
        probe_version=False,
    )

    assert manifest["model"]["requested"] == "requested-alias"
    assert manifest["model"]["resolved"] == "provider/canonical-model"
    assert manifest["model"]["resolution"] == "harness_reported"
    assert manifest["model"]["provider"] == "local"


def test_executable_probe_is_best_effort(monkeypatch):
    monkeypatch.setattr("aios_bench.manifest.shutil.which", lambda command: "/opt/bin/harness")
    monkeypatch.setattr(
        "aios_bench.manifest.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="Harness 1.2.3\nextra detail\n", stderr="", returncode=0
        ),
    )

    assert probe_executable("harness") == {
        "command": "harness",
        "path": "/opt/bin/harness",
        "version": "Harness 1.2.3",
        "probe_status": "ok",
    }


def test_configuration_sanitization_is_recursive():
    safe = sanitize_configuration(
        {"nested": {"Authorization": "Bearer value", "retries": 2}, "password": "value"}
    )

    assert safe == {
        "nested": {"Authorization": "[redacted]", "retries": 2},
        "password": "[redacted]",
    }


def test_empty_invocation_has_a_skipped_executable_probe():
    manifest = build_run_manifest(
        StructuredDelegationAdapter(), AgentInvocation([], {}), probe_version=False
    )

    assert manifest["harness"]["executable"] == {
        "command": None,
        "path": None,
        "version": None,
        "probe_status": "skipped",
    }
