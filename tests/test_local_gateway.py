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


def test_goose_binding_pins_provider_main_fast_model_and_writable_root(monkeypatch, tmp_path: Path):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://192.168.1.20:8080/v1")
    monkeypatch.delenv("AIOS_BENCH_GOOSE_PROVIDER", raising=False)
    invocation = AGENTS["goose"].adapter.build("task", workspace, "Ornith")

    provider_index = invocation.command.index("--provider")
    prompt_index = invocation.command.index("-t")
    assert invocation.command[provider_index + 1] == "openai"
    assert provider_index < prompt_index
    assert invocation.command[prompt_index + 1] == "task"
    assert invocation.environment["GOOSE_MODEL"] == "Ornith"
    assert invocation.environment["GOOSE_FAST_MODEL"] == "Ornith"
    assert invocation.environment["GOOSE_PATH_ROOT"] == "/tmp/aios-bench-goose"
    assert invocation.environment["OPENAI_HOST"] == "http://192.168.1.20:8080"
    assert invocation.environment["OPENAI_BASE_PATH"] == "v1/chat/completions"
    assert invocation.configuration["runtime_state_root"] == "/tmp/aios-bench-goose"


def test_letta_binding_forces_current_local_backend_and_isolated_state(monkeypatch, tmp_path: Path):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    invocation = AGENTS["letta"].adapter.build("task", workspace, "Ornith")

    backend_index = invocation.command.index("--backend")
    prompt_mode_index = invocation.command.index("-p")
    model_index = invocation.command.index("--model")
    assert invocation.command[backend_index + 1] == "local"
    assert backend_index < prompt_mode_index
    assert invocation.command[model_index + 1] == "llama-cpp/Ornith"
    assert invocation.provider == "llama-cpp"
    assert invocation.environment["LLAMA_CPP_BASE_URL"] == "http://127.0.0.1:8080/v1"
    assert invocation.environment["LETTA_LOCAL_BACKEND_DIR"].startswith("/tmp/")
    assert invocation.configuration["backend"] == "local"
    assert invocation.configuration["runtime_state_root"] == "/tmp/aios-bench-letta"


def test_hermes_binding_forces_openai_route_and_writable_home(monkeypatch, tmp_path: Path):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1")
    monkeypatch.delenv("AIOS_BENCH_HERMES_PROVIDER", raising=False)
    invocation = AGENTS["hermes"].adapter.build("task", workspace, "Ornith")

    provider_index = invocation.command.index("--provider")
    prompt_index = invocation.command.index("-z")
    assert invocation.command[provider_index + 1] == "openai-api"
    assert provider_index < prompt_index
    assert invocation.command[prompt_index + 1] == "task"
    assert invocation.provider == "openai-api"
    assert invocation.environment["OPENAI_BASE_URL"] == "http://127.0.0.1:8080/v1"
    assert invocation.environment["HERMES_HOME"] == "/tmp/aios-bench-hermes"
    assert invocation.configuration["runtime_state_root"] == "/tmp/aios-bench-hermes"


def test_claude_custom_gateway_gets_noninteractive_placeholder_when_no_auth_exists(
    monkeypatch,
    tmp_path: Path,
):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_CLAUDE_BASE_URL", "http://127.0.0.1:8081/v1")
    for key in (
        "AIOS_BENCH_CLAUDE_API_KEY",
        "AIOS_BENCH_CLAUDE_AUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "AIOS_BENCH_OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    invocation = AGENTS["claude"].adapter.build("task", workspace, "Ornith")

    assert invocation.environment["ANTHROPIC_API_KEY"] == "aios-bench-local"
    assert invocation.configuration["api_key_configured"] is True
    assert invocation.configuration["api_key_source"] == "benchmark_local_placeholder"
    assert invocation.configuration["gateway_auth_strategy"] == "benchmark_local_placeholder"


def test_claude_custom_gateway_preserves_explicit_benchmark_credential(monkeypatch, tmp_path: Path):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_CLAUDE_BASE_URL", "http://127.0.0.1:8081/v1")
    monkeypatch.setenv("AIOS_BENCH_CLAUDE_API_KEY", "configured-secret")

    invocation = AGENTS["claude"].adapter.build("task", workspace, "Ornith")

    assert invocation.environment["ANTHROPIC_API_KEY"] == "configured-secret"
    assert invocation.configuration["gateway_auth_strategy"] == "explicit_or_inherited_credential"
    assert invocation.configuration.get("api_key_source") != "benchmark_local_placeholder"


def test_claude_first_party_endpoint_does_not_invent_credentials(monkeypatch, tmp_path: Path):
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("AIOS_BENCH_CLAUDE_BASE_URL", "https://api.anthropic.com")
    for key in (
        "AIOS_BENCH_CLAUDE_API_KEY",
        "AIOS_BENCH_CLAUDE_AUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)

    invocation = AGENTS["claude"].adapter.build("task", workspace, "Ornith")

    assert "ANTHROPIC_API_KEY" not in invocation.environment
    assert invocation.configuration["api_key_configured"] is False
    assert invocation.configuration["auth_token_configured"] is False


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
