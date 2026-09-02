from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit


DEEPSEEK_PROVIDER_ID = "aios-bench-local"
DEEPSEEK_SANDBOX_HOME = Path("/tmp/aios-bench-deepseek")
DEEPSEEK_SETTINGS_FILENAME = "settings.yaml"
DEEPSEEK_API_KEY_ENV = "AIOS_BENCH_DEEPSEEK_API_KEY"


def _run_dir_for_workspace(workspace: Path) -> Path:
    """Return the owning run directory for a canonical task workspace.

    ``BenchmarkRunner`` also calls adapters once with the run directory itself
    while constructing execution identity, so non-workspace paths are already
    the desired owner and are returned unchanged.
    """

    resolved = workspace.resolve()
    if resolved.parent.name == "workspaces":
        return resolved.parent.parent
    return resolved


def settings_path(workspace: Path) -> Path:
    """Return the benchmark-owned, agent-hidden DeepSeek settings source."""

    return _run_dir_for_workspace(workspace) / "harness_config" / "deepseek" / DEEPSEEK_SETTINGS_FILENAME


def validate_endpoint(value: str) -> str:
    """Validate a credential-free HTTP(S) OpenAI-compatible endpoint.

    The generated settings document is retained with the run for auditability,
    so secrets must never be embedded in its URL. Authenticated deployments
    should use ``AIOS_BENCH_DEEPSEEK_API_KEY`` instead.
    """

    endpoint = value.strip().rstrip("/")
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("DeepSeek Harness requires an absolute http(s) AIOS_BENCH_ENDPOINT")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(
            "DeepSeek Harness endpoint must not contain credentials, query, or fragment; "
            f"use {DEEPSEEK_API_KEY_ENV} for authentication"
        )
    return endpoint


def _quoted(value: str) -> str:
    # JSON strings are valid YAML scalars and avoid hand-rolled escaping.
    return json.dumps(value, ensure_ascii=False)


def render_settings(*, endpoint: str, model: str) -> str:
    """Render the minimal settings layer required by the built-in headless profile."""

    endpoint = validate_endpoint(endpoint)
    model = model.strip()
    if not model:
        raise ValueError("DeepSeek Harness requires an explicit model id")
    return (
        "llm-pi-ai:\n"
        "  providers:\n"
        f"    {DEEPSEEK_PROVIDER_ID}:\n"
        "      displayName: \"AIOS-Bench Local\"\n"
        f"      apiKeyEnv: {DEEPSEEK_API_KEY_ENV}\n"
        "      api: openai-completions\n"
        f"      baseURL: {_quoted(endpoint)}\n"
        "      compat:\n"
        "        supportsDeveloperRole: false\n"
        "        maxTokensField: max_tokens\n"
        "      models:\n"
        f"        - id: {_quoted(model)}\n"
        "agent-default-model:\n"
        f"  provider: {DEEPSEEK_PROVIDER_ID}\n"
        f"  model: {_quoted(model)}\n"
    )


def write_settings(workspace: Path, *, endpoint: str, model: str) -> Path:
    """Atomically write the non-secret settings source retained with the run."""

    path = settings_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(render_settings(endpoint=endpoint, model=model), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    return path
