from __future__ import annotations

from pathlib import Path

import pytest

from aios_bench.deepseek_adapter import DeepSeekHarnessAdapter
from aios_bench.deepseek_runtime import (
    DEEPSEEK_API_KEY_ENV,
    DEEPSEEK_PROVIDER_ID,
    DEEPSEEK_SANDBOX_HOME,
    settings_path,
)
from aios_bench.manifest import build_run_manifest
from aios_bench.sandbox import workspace_sandbox


def test_deepseek_adapter_pins_headless_model_and_isolates_home(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    monkeypatch.setenv(DEEPSEEK_API_KEY_ENV, "private-key")

    adapter = DeepSeekHarnessAdapter()
    invocation = adapter.build("do the benchmark task", tmp_path, "local/Ornith")

    assert invocation.command == ["dsh", "--profile", "headless", "do the benchmark task"]
    assert invocation.environment["DSH_HOME"] == str(DEEPSEEK_SANDBOX_HOME)
    assert invocation.environment["DSH_PERMISSION_MODE"] == "danger-full-access"
    assert invocation.environment["DSH_TELEMETRY_DISABLED"] == "1"
    assert invocation.environment[DEEPSEEK_API_KEY_ENV] == "private-key"
    assert invocation.requested_model == "local/Ornith"
    assert invocation.resolved_model == "local/Ornith"
    assert invocation.provider == DEEPSEEK_PROVIDER_ID
    assert invocation.endpoint == "http://127.0.0.1:8080/v1"

    document = settings_path(tmp_path).read_text(encoding="utf-8")
    assert "provider: aios-bench-local" in document
    assert 'model: "local/Ornith"' in document
    assert 'baseURL: "http://127.0.0.1:8080/v1"' in document
    assert "supportsDeveloperRole: false" in document
    assert "maxTokensField: max_tokens" in document
    assert "private-key" not in document

    manifest = build_run_manifest(adapter, invocation, probe_version=False)
    assert manifest["model"]["requested"] == "local/Ornith"
    assert manifest["model"]["resolved"] == "local/Ornith"
    assert manifest["model"]["provider"] == DEEPSEEK_PROVIDER_ID
    assert manifest["model"]["endpoint"] == "http://127.0.0.1:8080/v1"
    assert manifest["configuration"]["ambient_dsh_home_inherited"] is False
    assert manifest["configuration"]["structured_events_available"] is False
    assert "private-key" not in str(manifest)


def test_deepseek_adapter_uses_dummy_key_for_no_auth_local_endpoint(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    monkeypatch.delenv(DEEPSEEK_API_KEY_ENV, raising=False)

    invocation = DeepSeekHarnessAdapter().build("task", tmp_path, "model")

    assert invocation.environment[DEEPSEEK_API_KEY_ENV] == "aios-bench-local"
    assert invocation.configuration["api_key_configured"] is False


def test_deepseek_adapter_fails_closed_without_explicit_endpoint_or_model(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("AIOS_BENCH_ENDPOINT", raising=False)
    with pytest.raises(ValueError, match="AIOS_BENCH_ENDPOINT"):
        DeepSeekHarnessAdapter().build("task", tmp_path, "model")

    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    with pytest.raises(ValueError, match="explicit model"):
        DeepSeekHarnessAdapter().build("task", tmp_path, "unknown")


def test_deepseek_endpoint_rejects_embedded_credentials(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://user:secret@127.0.0.1:8080/v1?token=x")
    with pytest.raises(ValueError, match="must not contain credentials"):
        DeepSeekHarnessAdapter().build("task", tmp_path, "model")


def test_deepseek_sandbox_mounts_settings_into_private_tmp_home(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    DeepSeekHarnessAdapter().build("task", tmp_path, "model")
    monkeypatch.setattr(
        "aios_bench.sandbox.shutil.which",
        lambda name: "/usr/bin/bwrap" if name == "bwrap" else None,
    )

    plan = workspace_sandbox("deepseek", tmp_path)

    source = str(settings_path(tmp_path).resolve())
    target = str(DEEPSEEK_SANDBOX_HOME / "settings.yaml")
    prefix = list(plan.command_prefix)
    assert plan.write_confined is True
    assert plan.grader_hidden is True
    assert plan.strategy.endswith("_deepseek_ephemeral_home")
    index = prefix.index(source)
    assert prefix[index - 1] == "--ro-bind"
    assert prefix[index + 1] == target


def test_deepseek_settings_are_captured_before_repository_mask(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    runtime = repo / ".venv"
    (runtime / "bin").mkdir(parents=True)
    workspace = (
        repo / "results" / ".local" / "deepseek" / "m" / "runs" / "r"
        / "workspaces" / "t"
    )
    workspace.mkdir(parents=True)

    # Tests import the historical aios_bench compatibility namespace, while the
    # callable retains the canonical core.benchmark module globals. Patch the
    # function's actual execution namespace rather than relying on the alias.
    sandbox_globals = workspace_sandbox.__globals__
    monkeypatch.setitem(sandbox_globals, "REPO_ROOT", repo)
    monkeypatch.setitem(sandbox_globals, "PROJECT_VENV", runtime)
    monkeypatch.setattr(
        sandbox_globals["shutil"],
        "which",
        lambda name: "/usr/bin/bwrap" if name == "bwrap" else None,
    )
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    DeepSeekHarnessAdapter().build("task", workspace, "model")

    prefix = list(workspace_sandbox("deepseek", workspace, "required").command_prefix)
    source = str(settings_path(workspace).resolve())
    source_index = prefix.index(source)
    repo_hide_index = next(
        index
        for index in range(len(prefix) - 1)
        if prefix[index] == "--tmpfs" and prefix[index + 1] == str(repo.resolve())
    )

    assert source_index < repo_hide_index


def test_deepseek_sandbox_fails_closed_without_bubblewrap(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="DeepSeek Harness isolation requires bubblewrap"):
        workspace_sandbox("deepseek", tmp_path)


def test_deepseek_sandbox_cannot_be_disabled(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "aios_bench.sandbox.shutil.which",
        lambda name: "/usr/bin/bwrap" if name == "bwrap" else None,
    )
    with pytest.raises(RuntimeError, match="requires the AIOS-Bench Bubblewrap sandbox"):
        workspace_sandbox("deepseek", tmp_path, "off")


def test_deepseek_does_not_claim_unobservable_browser_or_subagent_events():
    capabilities = DeepSeekHarnessAdapter.capabilities
    assert "terminal" in capabilities
    assert "skills" in capabilities
    assert "delegation" in capabilities
    assert "browser" not in capabilities
    assert "structured_subagent_events" not in capabilities
    assert "tool_events" not in capabilities
    assert "json_events" not in capabilities
