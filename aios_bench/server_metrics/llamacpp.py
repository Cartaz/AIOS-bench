from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .base import MetricsSnapshot, ServerMetricsClient


_LINE = re.compile(
    r"^([A-Za-z_:][A-Za-z0-9_:]*)(?:\{[^}]*\})?\s+"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|NaN|[+-]?Inf)(?:\s+\d+)?$"
)
_COUNTERS = (
    "prompt_tokens_total",
    "prompt_seconds_total",
    "tokens_predicted_total",
    "tokens_predicted_seconds_total",
)
_GAUGES = (
    "requests_processing",
    "requests_deferred",
    "n_tokens_max",
    "kv_cache_usage_ratio",
    "kv_cache_tokens",
)


def _normalize_name(name: str) -> str:
    if name.startswith("llamacpp:"):
        return name.removeprefix("llamacpp:")
    if name.startswith("llamacpp_"):
        return name.removeprefix("llamacpp_")
    return name


def parse_prometheus_metrics(text: str) -> dict[str, float]:
    """Parse the numeric subset needed from llama.cpp Prometheus exposition."""
    values: dict[str, float] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE.match(line)
        if not match:
            continue
        name = _normalize_name(match.group(1))
        if name not in {*_COUNTERS, *_GAUGES}:
            continue
        try:
            value = float(match.group(2))
        except ValueError:
            continue
        if not math.isfinite(value):
            continue
        # Router/model labels can produce multiple samples. Counters and the
        # aggregate queue gauges are additive for the selected endpoint.
        values[name] = values.get(name, 0.0) + value
    return values


def _public_url(url: str) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    return urlunsplit((parsed.scheme, f"{host}{port}", parsed.path, "", ""))


class LlamaCppMetricsClient(ServerMetricsClient):
    source = "llamacpp_prometheus"
    enabled = True

    def __init__(self, url: str, *, model: str | None = None, timeout: float = 0.75) -> None:
        parsed = urlsplit(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if model and "model" not in query:
            query["model"] = model
        self.url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))
        self.timeout = max(0.1, float(timeout))

    @property
    def public_endpoint(self) -> str | None:
        return _public_url(self.url)

    def snapshot(self) -> MetricsSnapshot:
        try:
            request = Request(
                self.url,
                headers={"Accept": "text/plain", "User-Agent": "AIOS-bench/server-metrics"},
            )
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - explicit benchmark endpoint
                text = response.read(1024 * 1024).decode("utf-8", errors="replace")
            values = parse_prometheus_metrics(text)
            if not values:
                return MetricsSnapshot(False, error="metrics endpoint returned no recognized llama.cpp metrics")
            return MetricsSnapshot(True, values=values)
        except Exception as exc:  # metrics must never make a benchmark task fail
            return MetricsSnapshot(False, error=f"{type(exc).__name__}: {exc}"[:500])

    def delta(self, before: MetricsSnapshot, after: MetricsSnapshot) -> dict[str, Any]:
        if not before.available or not after.available:
            return {
                "available": False,
                "usage_source": "unavailable",
                "trusted_for_efficiency": False,
                "error": after.error or before.error or "metrics snapshot unavailable",
            }

        deltas: dict[str, float] = {}
        resets: list[str] = []
        for name in _COUNTERS:
            if name not in before.values or name not in after.values:
                continue
            value = after.values[name] - before.values[name]
            if value < -1e-9:
                resets.append(name)
            else:
                deltas[name] = max(0.0, value)
        if resets:
            return {
                "available": False,
                "usage_source": "unavailable",
                "trusted_for_efficiency": False,
                "counter_reset": True,
                "reset_metrics": resets,
                "error": "llama.cpp metrics counter reset during task",
            }

        prompt_tokens = deltas.get("prompt_tokens_total")
        output_tokens = deltas.get("tokens_predicted_total")
        prompt_seconds = deltas.get("prompt_seconds_total")
        generation_seconds = deltas.get("tokens_predicted_seconds_total")
        token_counters_present = prompt_tokens is not None and output_tokens is not None

        result: dict[str, Any] = {
            "available": bool(deltas),
            "usage_source": "server_verified" if token_counters_present else "server_partial",
            "trusted_for_efficiency": token_counters_present,
            "counter_reset": False,
            "prompt_tokens": int(round(prompt_tokens)) if prompt_tokens is not None else None,
            "output_tokens": int(round(output_tokens)) if output_tokens is not None else None,
            "prompt_seconds": prompt_seconds,
            "generation_seconds": generation_seconds,
            "requests_processing_before": before.values.get("requests_processing"),
            "requests_processing_after": after.values.get("requests_processing"),
            "requests_deferred_before": before.values.get("requests_deferred"),
            "requests_deferred_after": after.values.get("requests_deferred"),
            "n_tokens_max_before": before.values.get("n_tokens_max"),
            "n_tokens_max_after": after.values.get("n_tokens_max"),
        }
        if prompt_tokens is not None and prompt_seconds and prompt_seconds > 0:
            result["prompt_tokens_per_second"] = prompt_tokens / prompt_seconds
        else:
            result["prompt_tokens_per_second"] = None
        if output_tokens is not None and generation_seconds and generation_seconds > 0:
            result["generation_tokens_per_second"] = output_tokens / generation_seconds
        else:
            result["generation_tokens_per_second"] = None
        return result
