from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

from .base import MetricsSnapshot, NullServerMetricsClient, OutputTokenGuard, ServerMetricsClient
from .llamacpp import LlamaCppMetricsClient, parse_prometheus_metrics


def _normalize_metrics_url(value: str) -> str:
    raw = value.strip()
    if not raw:
        return raw
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/")
    if not path:
        path = "/metrics"
    elif not path.endswith("/metrics") and path != "/metrics":
        path += "/metrics"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def _metrics_url_from_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    raw = endpoint.strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, "/metrics", "", ""))


def build_server_metrics_client(
    url: str | None = None,
    *,
    endpoint: str | None = None,
    model: str | None = None,
) -> ServerMetricsClient:
    configured = url or os.environ.get("AIOS_BENCH_SERVER_METRICS_URL")
    if not configured:
        configured = _metrics_url_from_endpoint(endpoint or os.environ.get("AIOS_BENCH_ENDPOINT"))
    if not configured:
        return NullServerMetricsClient()
    selected_model = model or os.environ.get("AIOS_BENCH_SERVER_METRICS_MODEL")
    return LlamaCppMetricsClient(_normalize_metrics_url(configured), model=selected_model)


__all__ = [
    "MetricsSnapshot",
    "NullServerMetricsClient",
    "OutputTokenGuard",
    "ServerMetricsClient",
    "LlamaCppMetricsClient",
    "build_server_metrics_client",
    "parse_prometheus_metrics",
]
