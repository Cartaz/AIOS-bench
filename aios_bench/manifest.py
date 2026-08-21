from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .adapters import Adapter, AgentInvocation


MANIFEST_SCHEMA = "aios-bench/run-manifest/v2"
_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
_SAFE_TOKEN_KEYS = frozenset({
    "max_tokens", "max_completion_tokens", "context_tokens", "input_tokens",
    "output_tokens", "prompt_tokens", "completion_tokens", "token_count", "tokenizer",
})
_REDACTED = "[redacted]"
_SECRET_VALUE = re.compile(
    r"(?i)(?:^|\s)(?:authorization|api[_-]?key|password|secret|token)\s*[:=]|^bearer\s+\S+"
)


def _is_secret_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    if normalized in _SAFE_TOKEN_KEYS:
        return False
    return any(marker in normalized for marker in _SECRET_MARKERS)


def _safe_text(value: object, limit: int = 1000) -> str:
    return str(value).replace("\x00", "").strip()[:limit]


def _fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _file_digest(path: str | None) -> str | None:
    if not path:
        return None
    model_path = Path(path).expanduser()
    if not model_path.is_file():
        return None
    digest = hashlib.sha256()
    with model_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _environment_json(name: str) -> dict[str, Any]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "parse_error": True,
            "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        }
    return value if isinstance(value, dict) else {"value": value}


def sanitize_configuration(value: Any, *, _key: object = "") -> Any:
    """Return a JSON-compatible copy with credential-bearing fields redacted."""
    if _is_secret_key(_key):
        return value if isinstance(value, bool) else _REDACTED
    if isinstance(value, Mapping):
        return {str(key): sanitize_configuration(item, _key=key) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [sanitize_configuration(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    text = _safe_text(value)
    return _REDACTED if _SECRET_VALUE.search(text) else text


def sanitize_endpoint(endpoint: str | None) -> str | None:
    """Keep endpoint identity while discarding user-info, query, and fragment."""
    if not endpoint:
        return None
    endpoint = _safe_text(endpoint)
    parsed = urlsplit(endpoint)
    if not parsed.scheme or not parsed.netloc:
        endpoint = endpoint.split("?", 1)[0].split("#", 1)[0]
        return endpoint.rsplit("@", 1)[-1]
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = f":{parsed.port}" if parsed.port is not None else ""
    except ValueError:
        port = ""
    return urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path, "", ""))


def probe_executable(command: str, *, timeout: float = 3.0) -> dict[str, object]:
    """Resolve and version an invocation executable without failing the run."""
    resolved = shutil.which(command)
    if resolved is None and Path(command).is_file():
        resolved = str(Path(command).resolve())
    result: dict[str, object] = {"command": command, "path": resolved, "version": None}
    if resolved is None:
        result["probe_status"] = "not_found"
        return result
    probe_environment = {"PATH": os.environ.get("PATH", ""), "LC_ALL": "C", "LANG": "C"}
    if os.name == "nt" and "SYSTEMROOT" in os.environ:
        probe_environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    try:
        completed = subprocess.run(
            [resolved, "--version"], capture_output=True, check=False,
            env=probe_environment, text=True, timeout=timeout,
        )
        output = completed.stdout.strip() or completed.stderr.strip()
        result["version"] = _safe_text(output.splitlines()[0], 500) if output else None
        result["probe_status"] = "ok" if completed.returncode == 0 and output else "unavailable"
    except (OSError, subprocess.SubprocessError):
        result["probe_status"] = "unavailable"
    return result


def build_run_manifest(
    adapter: Adapter,
    invocation: AgentInvocation,
    *,
    resolved_model: str | None = None,
    provider: str | None = None,
    endpoint: str | None = None,
    model_digest: str | None = None,
    inference_configuration: Mapping[str, Any] | None = None,
    configuration: Mapping[str, Any] | None = None,
    probe_version: bool = True,
) -> dict[str, object]:
    """Build stable, non-secret provenance and comparability metadata."""
    executable = (
        probe_executable(invocation.command[0])
        if probe_version and invocation.command
        else {
            "command": invocation.command[0] if invocation.command else None,
            "path": shutil.which(invocation.command[0]) if invocation.command else None,
            "version": None,
            "probe_status": "skipped",
        }
    )
    effective_model = resolved_model or invocation.resolved_model
    requested_model = invocation.requested_model
    if resolved_model:
        resolution = "harness_reported"
    elif invocation.resolved_model:
        resolution = "adapter_pinned"
    elif requested_model:
        resolution = "requested_unverified"
    else:
        resolution = "unreported"

    combined_configuration = dict(invocation.configuration)
    if configuration:
        combined_configuration.update(configuration)
    safe_configuration = sanitize_configuration(combined_configuration)

    declared_digest = model_digest or os.environ.get("AIOS_BENCH_MODEL_DIGEST")
    declared_digest = _safe_text(declared_digest, 500) if declared_digest else None
    computed_digest = _file_digest(os.environ.get("AIOS_BENCH_MODEL_FILE"))
    digest_mismatch = bool(computed_digest and declared_digest and computed_digest != declared_digest)
    digest = computed_digest or declared_digest
    provider_value = provider or invocation.provider or os.environ.get("AIOS_BENCH_PROVIDER")
    endpoint_value = endpoint or invocation.endpoint or os.environ.get("AIOS_BENCH_ENDPOINT")
    inference = dict(_environment_json("AIOS_BENCH_INFERENCE_CONFIG"))
    if inference_configuration:
        inference.update(inference_configuration)
    safe_inference = sanitize_configuration(inference)

    model_identity = {
        "resolved": effective_model,
        "digest": digest,
        "provider": _safe_text(provider_value) if provider_value else None,
        "endpoint": sanitize_endpoint(endpoint_value),
        "inference": safe_inference,
    }
    verification = (
        "digest_mismatch" if digest_mismatch
        else "verified_file_digest" if effective_model and computed_digest
        else "declared_digest" if effective_model and declared_digest
        else "declared_model" if effective_model
        else "unverified"
    )

    return {
        "schema": MANIFEST_SCHEMA,
        "harness": {
            "name": adapter.name,
            "capabilities": sorted(adapter.capabilities),
            "executable": executable,
        },
        "model": {
            "requested": requested_model,
            "resolved": effective_model,
            "resolution": resolution,
            "digest": digest,
            "verification": verification,
            "strictly_comparable": bool(effective_model and digest and not digest_mismatch),
            "digest_source": "model_file" if computed_digest else "declared" if declared_digest else None,
            "digest_mismatch": digest_mismatch,
            "identity_fingerprint": _fingerprint(model_identity),
            "provider": model_identity["provider"],
            "endpoint": model_identity["endpoint"],
        },
        "inference": safe_inference,
        "configuration": safe_configuration,
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": sys.platform,
            "machine": platform.machine(),
        },
    }
