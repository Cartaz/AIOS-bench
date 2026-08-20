from __future__ import annotations

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


MANIFEST_SCHEMA = "aios-bench/run-manifest/v1"
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
_REDACTED = "[redacted]"
_SECRET_VALUE = re.compile(
    r"(?i)(?:^|\s)(?:authorization|api[_-]?key|password|secret|token)\s*[:=]|^bearer\s+\S+"
)


def _is_secret_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return any(marker in normalized for marker in _SECRET_MARKERS)


def _safe_text(value: object, limit: int = 1000) -> str:
    text = str(value).replace("\x00", "").strip()
    return text[:limit]


def sanitize_configuration(value: Any, *, _key: object = "") -> Any:
    """Return a JSON-compatible copy with credential-bearing fields redacted."""

    if _is_secret_key(_key):
        # Presence flags are useful provenance and cannot disclose the value.
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
        # Local socket paths and non-URL endpoint names are still useful.
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

    probe_environment = {
        "PATH": os.environ.get("PATH", ""),
        "LC_ALL": "C",
        "LANG": "C",
    }
    if os.name == "nt" and "SYSTEMROOT" in os.environ:
        probe_environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    try:
        completed = subprocess.run(
            [resolved, "--version"],
            capture_output=True,
            check=False,
            env=probe_environment,
            text=True,
            timeout=timeout,
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
    configuration: Mapping[str, Any] | None = None,
    probe_version: bool = True,
) -> dict[str, object]:
    """Build stable, non-secret provenance metadata for a benchmark run.

    ``resolved_model`` is an optional observation from the harness.  When it is
    absent, an adapter may still report a model it explicitly pinned on its
    command line.  The invocation command and environment are intentionally not
    serialized because they contain the task prompt and can contain API keys.
    """

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
            "provider": _safe_text(provider or invocation.provider) if (provider or invocation.provider) else None,
            "endpoint": sanitize_endpoint(endpoint or invocation.endpoint),
        },
        "configuration": sanitize_configuration(combined_configuration),
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": sys.platform,
            "machine": platform.machine(),
        },
    }
