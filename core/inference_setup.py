from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit, urlunsplit


DEFAULT_PROBE_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class GatewayProbeResult:
    kind: str
    endpoint: str
    model: str
    reachable: bool
    model_found: bool
    inference_ok: bool
    available_models: tuple[str, ...] = ()
    resolved_model: str | None = None
    error: str | None = None

    @property
    def ready(self) -> bool:
        return self.reachable and self.model_found and self.inference_ok

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "endpoint": self.endpoint,
            "model": self.model,
            "reachable": self.reachable,
            "model_found": self.model_found,
            "inference_ok": self.inference_ok,
            "available_models": list(self.available_models),
            "resolved_model": self.resolved_model,
            "ready": self.ready,
            "error": self.error,
        }


def normalize_endpoint(value: str, *, anthropic: bool = False) -> str:
    """Validate and normalize a user-supplied local inference endpoint.

    Credentials, query strings and fragments are rejected so saved settings and
    run provenance never accidentally retain secrets. OpenAI-compatible URLs are
    expected to include their API prefix (normally ``/v1``). Anthropic base URLs
    are stored at the service root because Claude Code appends ``/v1/messages``.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Endpoint must be an http:// or https:// URL with a host")
    if parsed.username or parsed.password:
        raise ValueError("Endpoint URLs must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("Endpoint URLs must not contain query strings or fragments")

    hostname = parsed.hostname
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = f":{parsed.port}" if parsed.port is not None else ""
    except ValueError as exc:
        raise ValueError("Endpoint contains an invalid port") from exc
    path = parsed.path.rstrip("/")
    if anthropic and path == "/v1":
        path = ""
    return urlunsplit((parsed.scheme, f"{hostname}{port}", path, "", ""))


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
) -> object:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Accept": "application/json"}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        url,
        data=payload,
        headers=request_headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _error_text(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"
    if isinstance(exc, urllib.error.URLError):
        return f"Connection failed: {exc.reason}"
    return str(exc) or exc.__class__.__name__


def discover_openai_models(
    endpoint: str,
    *,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    cancellation_check: Callable[[], bool] | None = None,
) -> tuple[str, tuple[str, ...]]:
    base = normalize_endpoint(endpoint)
    if not base:
        raise ValueError("OpenAI-compatible endpoint is required")
    if cancellation_check is not None and cancellation_check():
        raise RuntimeError("Inference setup cancelled")
    value = _request_json(f"{base}/models", timeout=timeout)
    if cancellation_check is not None and cancellation_check():
        raise RuntimeError("Inference setup cancelled")
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        raise RuntimeError("/models did not return an OpenAI-compatible model list")
    models = []
    for item in value["data"]:
        if isinstance(item, dict):
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id.strip():
                models.append(model_id.strip())
    return base, tuple(dict.fromkeys(models))


def probe_openai_gateway(
    endpoint: str,
    model: str,
    *,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    cancellation_check: Callable[[], bool] | None = None,
) -> GatewayProbeResult:
    requested = str(model or "").strip()
    if not requested:
        raise ValueError("Model id is required")
    try:
        base, models = discover_openai_models(
            endpoint,
            timeout=timeout,
            cancellation_check=cancellation_check,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        normalized = normalize_endpoint(endpoint) if str(endpoint or "").strip() else ""
        return GatewayProbeResult(
            "openai",
            normalized,
            requested,
            False,
            False,
            False,
            error=_error_text(exc),
        )

    if requested not in models:
        return GatewayProbeResult(
            "openai",
            base,
            requested,
            True,
            False,
            False,
            available_models=models,
            error="Selected model is not present in /models",
        )

    if cancellation_check is not None and cancellation_check():
        raise RuntimeError("Inference setup cancelled")
    api_key = os.environ.get("AIOS_BENCH_OPENAI_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = _request_json(
            f"{base}/chat/completions",
            method="POST",
            body={
                "model": requested,
                "messages": [{"role": "user", "content": "Reply with OK."}],
                "temperature": 0,
                "max_tokens": 8,
            },
            headers=headers,
            timeout=timeout,
        )
        if cancellation_check is not None and cancellation_check():
            raise RuntimeError("Inference setup cancelled")
        if not isinstance(response, dict) or not isinstance(response.get("choices"), list):
            raise RuntimeError("chat/completions returned an invalid OpenAI-compatible response")
        if not response["choices"]:
            raise RuntimeError("chat/completions returned no choices")
        returned = response.get("model")
        resolved = returned.strip() if isinstance(returned, str) and returned.strip() else requested
        if resolved != requested:
            raise RuntimeError(
                f"Server resolved model '{resolved}' instead of requested '{requested}'"
            )
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        return GatewayProbeResult(
            "openai",
            base,
            requested,
            True,
            True,
            False,
            available_models=models,
            error=_error_text(exc),
        )

    return GatewayProbeResult(
        "openai",
        base,
        requested,
        True,
        True,
        True,
        available_models=models,
        resolved_model=resolved,
    )


def probe_anthropic_gateway(
    endpoint: str,
    model: str,
    *,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    cancellation_check: Callable[[], bool] | None = None,
) -> GatewayProbeResult:
    requested = str(model or "").strip()
    if not requested:
        raise ValueError("Model id is required")
    try:
        base = normalize_endpoint(endpoint, anthropic=True)
    except ValueError as exc:
        return GatewayProbeResult(
            "anthropic", "", requested, False, False, False, error=str(exc)
        )
    if not base:
        return GatewayProbeResult(
            "anthropic",
            "",
            requested,
            False,
            False,
            False,
            error="Anthropic-compatible endpoint is not configured",
        )
    if cancellation_check is not None and cancellation_check():
        raise RuntimeError("Inference setup cancelled")

    api_key = os.environ.get("AIOS_BENCH_CLAUDE_API_KEY", "").strip() or "aios-bench-local"
    try:
        response = _request_json(
            f"{base}/v1/messages",
            method="POST",
            body={
                "model": requested,
                "max_tokens": 8,
                "messages": [{"role": "user", "content": "Reply with OK."}],
            },
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=timeout,
        )
        if cancellation_check is not None and cancellation_check():
            raise RuntimeError("Inference setup cancelled")
        if not isinstance(response, dict):
            raise RuntimeError("/v1/messages returned a non-object response")
        returned = response.get("model")
        resolved = returned.strip() if isinstance(returned, str) and returned.strip() else requested
        if resolved != requested:
            raise RuntimeError(
                f"Anthropic gateway resolved model '{resolved}' instead of requested '{requested}'"
            )
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        return GatewayProbeResult(
            "anthropic",
            base,
            requested,
            True,
            True,
            False,
            resolved_model=None,
            error=_error_text(exc),
        )

    return GatewayProbeResult(
        "anthropic",
        base,
        requested,
        True,
        True,
        True,
        resolved_model=resolved,
    )
