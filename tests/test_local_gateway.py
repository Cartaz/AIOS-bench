from __future__ import annotations

import json
from pathlib import Path

from core.benchmark.harness_registry import AGENTS
from core.benchmark.local_gateway import binding_summary, profile_source_dir


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "runs" / "run-1" / "workspaces" / "task-1"
    workspace.mkdir(parents=True)
    return workspace


def test_pi_binding_uses_benchmark_owned_models_file(monkeypatch, tmp_path: Path):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    invocation = AGENTS["piagent"].adapter.build("task", workspace, "aios-llamacpp/Ornith")

    assert invocation.provider == "aios-bench"
    assert invocation.endpoint == "http://127.0.0.1:8080/v1"
    assert invocation.requested_model == "aios-llamacpp/Ornith"
    assert invocation.resolved_model == "aios-llamacpp/Ornith"
    model_index = invocation.command.index("--model")
    assert invocation.command[model_index + 1] == "aios-bench/aios-llamacpp/Ornith"
    profile = profile_source_dir(workspace, "piagent") / "models.json"
    value = json.loads(profile.read_text(encoding="utf-8"))
    provider = value["providers"]["aios-bench"]
    assert provider["baseUrl"] == "http://127.0.0.1:8080/v1"
    assert provider["models"] == [{"id": "aios-llamacpp/Ornith"}]
    assert "secret" not in profile.read_text(encoding="utf-8")


def test_opencode_binding_uses_pinned_stable_inline_provider_schema(monkeypatch, tmp_path: Path):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    monkeypatch.delenv("AIOS_BENCH_OPENAI_API_KEY", raising=False)
    invocation = AGENTS["opencode"].adapter.build("task", workspace, "Ornith")

    assert invocation.provider == "aios-bench"
    assert invocation.model_resolution == "aios_bench_gateway_profile"
    model_index = invocation.command.index("--model")
    assert invocation.command[model_index + 1] == "aios-bench/Ornith"
    config = json.loads(invocation.environment["OPENCODE_CONFIG_CONTENT"])
    assert config["model"] == "aios-bench/Ornith"
    assert config["small_model"] == "aios-bench/Ornith"
    provider = config["provider"]["aios-bench"]
    assert provider["npm"] == "@ai-sdk/openai-compatible"
    assert provider["options"] == {"baseURL": "http://127.0.0.1:8080/v1"}
    assert provider["models"]["Ornith"] == {"name": "Ornith"}
    assert "providers" not in config
    assert "package" not in provider
    assert "settings" not in provider


def test_opencode_binding_references_api_key_without_embedding_secret(monkeypatch, tmp_path: Path):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    monkeypatch.setenv("AIOS_BENCH_OPENAI_API_KEY", "super-secret")
    invocation = AGENTS["opencode"].adapter.build("task", workspace, "Ornith")

    raw_config = invocation.environment["OPENCODE_CONFIG_CONTENT"]
    config = json.loads(raw_config)
    options = config["provider"]["aios-bench"]["options"]
    assert options["apiKey"] == "{env:AIOS_BENCH_OPENAI_API_KEY}"
    assert invocation.environment["AIOS_BENCH_OPENAI_API_KEY"] == "super-secret"
    assert "super-secret" not in raw_config


def test_goose_binding_pins_provider_main_and_fast_model(monkeypatch, tmp_path: Path):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://192.168.1.20:8080/v1")
    invocation = AGENTS["goose"].adapter.build("task", workspace, "Ornith")

    provider_index = invocation.command.index("--provider")
    assert invocation.command[provider_index + 1] == "openai"
    assert invocation.environment["GOOSE_MODEL"] == "Ornith"
    assert invocation.environment["GOOSE_FAST_MODEL"] == "Ornith"
    assert invocation.environment["OPENAI_HOST"] == "http://192.168.1.20:8080"
    assert invocation.environment["OPENAI_BASE_PATH"] == "v1/chat/completions"


def test_letta_binding_uses_current_llama_cpp_provider(monkeypatch, tmp_path: Path):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    invocation = AGENTS["letta"].adapter.build("task", workspace, "Ornith")

    model_index = invocation.command.index("--model")
    assert invocation.command[model_index + 1] == "llama-cpp/Ornith"
    assert invocation.provider == "llama-cpp"
    assert invocation.environment["LLAMA_CPP_BASE_URL"] == "http://127.0.0.1:8080/v1"
    assert invocation.environment["LETTA_LOCAL_BACKEND_DIR"].startswith("/tmp/")


def test_hermes_binding_forces_openai_compatible_route(monkeypatch, tmp_path: Path):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    monkeypatch.setenv("AIOS_BENCH_HERMES_PROVIDER", "something-ambient")
    invocation = AGENTS["hermes"].adapter.build("task", workspace, "Ornith")

    provider_index = invocation.command.index("--provider")
    assert invocation.command[provider_index + 1] == "openai-api"
    assert invocation.provider == "openai-api"
    assert invocation.environment["OPENAI_BASE_URL"] == "http://127.0.0.1:8080/v1"


def test_binding_summary_keeps_claude_and_agentzero_limits_explicit():
    claude = binding_summary(
        "claude",
        endpoint="http://127.0.0.1:8080/v1",
        model="Ornith",
        anthropic_url="",
    )
    agentzero = binding_summary(
        "agentzero",
        endpoint="http://127.0.0.1:8080/v1",
        model="Ornith",
    )
    assert claude["status"] == "needs_anthropic_endpoint"
    assert claude["automatic"] is False
    assert agentzero["status"] == "external_service"
    assert agentzero["automatic"] is False
