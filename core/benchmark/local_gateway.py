from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


PROVIDER_ID = "aios-bench"
OPENAI_API_KEY_ENV = "AIOS_BENCH_OPENAI_API_KEY"


def _api_key() -> str:
    return os.environ.get(OPENAI_API_KEY_ENV, "").strip() or "aios-bench-local"


def profile_source_dir(workspace: Path, harness: str) -> Path:
    """Return a grader-side source directory for one harness profile.

    Real task workspaces store profiles under their run directory. Manifest-only
    adapter builds use an ``_manifest`` scope inside the run directory so probe
    construction never leaks state into a sibling run or the model directory.
    """
    workspace = workspace.resolve()
    if workspace.parent.name == "workspaces":
        run_dir = workspace.parent.parent
        scope = workspace.name
    elif workspace.parent.name == "runs":
        run_dir = workspace
        scope = "_manifest"
    else:
        run_dir = workspace.parent
        scope = workspace.name
    return run_dir / "harness_profiles" / scope / harness


def write_pi_profile(workspace: Path, *, endpoint: str, model: str) -> Path:
    directory = profile_source_dir(workspace, "piagent")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "models.json"
    payload = {
        "providers": {
            PROVIDER_ID: {
                "baseUrl": endpoint,
                "api": "openai-completions",
                "apiKey": f"${OPENAI_API_KEY_ENV}",
                "models": [{"id": model}],
            }
        }
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def pi_binding(workspace: Path, *, endpoint: str, model: str) -> tuple[str, dict[str, str]]:
    source = write_pi_profile(workspace, endpoint=endpoint, model=model)
    environment = {
        "PI_CODING_AGENT_DIR": str(source.parent),
        "PI_OFFLINE": "1",
        "PI_SKIP_VERSION_CHECK": "1",
        "PI_TELEMETRY": "0",
        OPENAI_API_KEY_ENV: _api_key(),
    }
    return f"{PROVIDER_ID}/{model}", environment


def opencode_binding(*, endpoint: str, model: str) -> tuple[str, dict[str, str]]:
    """Use the pinned OpenCode 1.18.x inline-config schema.

    Version 1.18 uses ``provider``/``npm``/``options`` rather than the future V2
    ``providers``/``package``/``settings`` shape. The real server model id is the
    key in ``provider.<id>.models``. Pin ``small_model`` to the same model so
    OpenCode cannot silently use a different auxiliary model for light tasks.
    """
    model_handle = f"{PROVIDER_ID}/{model}"
    provider: dict[str, object] = {
        "name": "AIOS-Bench local gateway",
        "npm": "@ai-sdk/openai-compatible",
        "options": {"baseURL": endpoint},
        "models": {model: {"name": model}},
    }
    configured_key = os.environ.get(OPENAI_API_KEY_ENV, "").strip()
    if configured_key:
        provider["options"] = {
            "baseURL": endpoint,
            "apiKey": f"{{env:{OPENAI_API_KEY_ENV}}}",
        }
    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": model_handle,
        "small_model": model_handle,
        "provider": {PROVIDER_ID: provider},
    }
    environment = {
        "OPENCODE_CONFIG_CONTENT": json.dumps(config, separators=(",", ":")),
        "OPENCODE_CONFIG_DIR": "/tmp/aios-bench-opencode/config",
        "XDG_CONFIG_HOME": "/tmp/aios-bench-opencode/xdg-config",
        "XDG_DATA_HOME": "/tmp/aios-bench-opencode/xdg-data",
        "XDG_STATE_HOME": "/tmp/aios-bench-opencode/xdg-state",
        "XDG_CACHE_HOME": "/tmp/aios-bench-opencode/xdg-cache",
    }
    if configured_key:
        environment[OPENAI_API_KEY_ENV] = configured_key
    return model_handle, environment


def _goose_route(endpoint: str) -> tuple[str, str]:
    parsed = urlsplit(endpoint)
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    host = urlunsplit((parsed.scheme, f"{hostname}{port}", "", "", ""))
    prefix = parsed.path.strip("/")
    path = f"{prefix}/chat/completions" if prefix else "v1/chat/completions"
    return host, path


def goose_binding(*, endpoint: str, model: str) -> dict[str, str]:
    host, base_path = _goose_route(endpoint)
    key = _api_key()
    return {
        "GOOSE_PROVIDER": "openai",
        "GOOSE_MODEL": model,
        "GOOSE_FAST_MODEL": model,
        "OPENAI_HOST": host,
        "OPENAI_BASE_PATH": base_path,
        "OPENAI_API_KEY": key,
    }


def letta_binding(*, endpoint: str, model: str) -> tuple[str, dict[str, str]]:
    return (
        f"llama-cpp/{model}",
        {
            "LLAMA_CPP_BASE_URL": endpoint,
            "LLAMA_CPP_API_KEY": _api_key(),
            "LETTA_LOCAL_BACKEND_DIR": "/tmp/aios-bench-letta/backend",
        },
    )


def hermes_binding(*, endpoint: str) -> dict[str, str]:
    return {
        "OPENAI_BASE_URL": endpoint,
        "OPENAI_API_KEY": _api_key(),
    }


def _set_flag(
    command: list[str],
    flag: str,
    value: str,
    *,
    before: str | None = None,
) -> list[str]:
    """Set an option without splitting a prompt-bearing flag from its value."""
    result = list(command)
    if flag in result:
        index = result.index(flag)
        if index + 1 >= len(result):
            raise RuntimeError(f"Malformed harness command: {flag} has no value")
        result[index + 1] = value
        return result
    if before is not None and before in result:
        insert_at = result.index(before)
    else:
        insert_at = max(len(result) - 1, 1)
    result[insert_at:insert_at] = [flag, value]
    return result


def bind_invocation(
    harness: str,
    invocation: Any,
    *,
    workspace: Path,
    model: str,
) -> Any:
    """Bind an adapter invocation to the canonical AIOS-Bench gateway profile.

    This is deliberately one post-build boundary rather than eight adapter
    special cases. It preserves concrete adapter types (notably Pi RPC) while
    replacing ambient provider configuration with benchmark-owned runtime state.
    """
    endpoint = os.environ.get("AIOS_BENCH_ENDPOINT", "").strip()
    requested = str(model or "").strip()
    if not endpoint or not requested or requested == "unknown":
        return invocation
    if harness in {"agentzero", "claude", "deepseek"}:
        return invocation

    command = list(invocation.command)
    environment = dict(invocation.environment)
    provider = invocation.provider
    effective_model = requested
    configuration = dict(invocation.configuration)

    if harness == "hermes":
        environment.update(hermes_binding(endpoint=endpoint))
        command = _set_flag(command, "--provider", "openai-api", before="-z")
        provider = "openai-api"
    elif harness == "piagent":
        effective_model, extra = pi_binding(workspace, endpoint=endpoint, model=requested)
        environment.update(extra)
        command = _set_flag(command, "--model", effective_model)
        provider = PROVIDER_ID
    elif harness == "opencode":
        effective_model, extra = opencode_binding(endpoint=endpoint, model=requested)
        environment.update(extra)
        command = _set_flag(command, "--model", effective_model)
        provider = PROVIDER_ID
    elif harness == "goose":
        environment.update(goose_binding(endpoint=endpoint, model=requested))
        command = _set_flag(command, "--provider", "openai", before="-t")
        provider = "openai"
    elif harness == "letta":
        effective_model, extra = letta_binding(endpoint=endpoint, model=requested)
        environment.update(extra)
        command = _set_flag(command, "--model", effective_model)
        provider = "llama-cpp"
    else:
        return invocation

    configuration.update(
        {
            "gateway_profile": "aios_bench_canonical",
            "gateway_configuration_scope": "isolated_runtime",
            "ambient_provider_configuration": False,
            "effective_model_handle": effective_model,
        }
    )
    return replace(
        invocation,
        command=command,
        environment=environment,
        requested_model=requested,
        resolved_model=requested,
        model_resolution="aios_bench_gateway_profile",
        provider=provider,
        endpoint=endpoint,
        configuration=configuration,
    )


def binding_summary(
    harness: str,
    *,
    endpoint: str,
    model: str,
    anthropic_url: str = "",
) -> dict[str, object]:
    """Describe how AIOS-Bench binds one harness without mutating user config."""
    automatic_openai = {"hermes", "piagent", "opencode", "goose", "letta", "deepseek"}
    if harness in automatic_openai:
        provider = {
            "hermes": "openai-api",
            "piagent": PROVIDER_ID,
            "opencode": PROVIDER_ID,
            "goose": "openai",
            "letta": "llama-cpp",
            "deepseek": PROVIDER_ID,
        }[harness]
        return {
            "status": "configured",
            "automatic": True,
            "provider": provider,
            "endpoint": endpoint,
            "model": model,
            "configuration_scope": "aios_bench_isolated_runtime",
        }
    if harness == "claude":
        return {
            "status": "configured" if anthropic_url else "needs_anthropic_endpoint",
            "automatic": bool(anthropic_url),
            "provider": "anthropic_compatible_gateway" if anthropic_url else None,
            "endpoint": anthropic_url or None,
            "model": model,
            "configuration_scope": "aios_bench_isolated_runtime",
        }
    if harness == "agentzero":
        return {
            "status": "external_service",
            "automatic": False,
            "provider": None,
            "endpoint": None,
            "model": model,
            "configuration_scope": "operator_attested_remote_service",
        }
    return {
        "status": "external_runtime",
        "automatic": False,
        "provider": None,
        "endpoint": endpoint or None,
        "model": model,
        "configuration_scope": "external_runtime",
    }
