from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


PROVIDER_ID = "aios-bench"
OPENAI_API_KEY_ENV = "AIOS_BENCH_OPENAI_API_KEY"


def _api_key() -> str:
    return os.environ.get(OPENAI_API_KEY_ENV, "").strip() or "aios-bench-local"


def profile_source_dir(workspace: Path, harness: str) -> Path:
    """Return a grader-side source directory for one task-scoped harness profile."""
    workspace = workspace.resolve()
    if workspace.parent.name == "workspaces":
        run_dir = workspace.parent.parent
    else:
        run_dir = workspace.parent
    return run_dir / "harness_profiles" / workspace.name / harness


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
    """Use inline runtime config so no personal OpenCode provider file is edited."""
    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": f"{PROVIDER_ID}/benchmark-model",
        "providers": {
            PROVIDER_ID: {
                "name": "AIOS-Bench local gateway",
                "package": "@opencode-ai/ai/providers/openai-compatible",
                "settings": {
                    "baseURL": endpoint,
                    "apiKey": "{env:AIOS_BENCH_OPENAI_API_KEY}",
                },
                "models": {
                    "benchmark-model": {
                        "modelID": model,
                        "name": model,
                    }
                },
            }
        },
    }
    environment = {
        "OPENCODE_CONFIG_CONTENT": json.dumps(config, separators=(",", ":")),
        "OPENCODE_CONFIG_DIR": "/tmp/aios-bench-opencode/config",
        "XDG_CONFIG_HOME": "/tmp/aios-bench-opencode/xdg-config",
        "XDG_DATA_HOME": "/tmp/aios-bench-opencode/xdg-data",
        "XDG_STATE_HOME": "/tmp/aios-bench-opencode/xdg-state",
        "XDG_CACHE_HOME": "/tmp/aios-bench-opencode/xdg-cache",
        OPENAI_API_KEY_ENV: _api_key(),
    }
    return f"{PROVIDER_ID}/benchmark-model", environment


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
