from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from dataclasses import fields
from urllib.parse import urlsplit, urlunsplit

from .resource_telemetry import ResourceSnapshot

RESOURCE_SCHEMA = "aios-bench/resource-snapshot/v1"
TOKEN_ENV = "AIOS_BENCH_RESOURCE_TOKEN"


def normalize_resource_url(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError("server resource URL must not be empty")
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("server resource URL must be an HTTP(S) URL")
    path = parsed.path.rstrip("/")
    if not path:
        path = "/v1/snapshot"
    elif not path.endswith("/v1/snapshot"):
        path += "/v1/snapshot"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def _valid_number(value: object, *, integer: bool = False, optional: bool = False) -> bool:
    if value is None:
        return optional
    if isinstance(value, bool):
        return False
    if integer:
        return isinstance(value, int) and value >= 0
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _validate_snapshot_values(values: dict[str, object]) -> None:
    required_ints = (
        "process_rss_bytes",
        "process_count",
        "host_ram_used_bytes",
    )
    required_numbers = (
        "captured_at",
        "process_cpu_percent",
        "host_cpu_percent",
    )
    optional_ints = (
        "process_vram_used_bytes",
        "process_gpu_client_count",
        "vram_used_bytes",
        "vram_total_bytes",
        "gpu_device_count",
    )
    optional_numbers = (
        "process_gpu_engine_time_percent",
        "gpu_busy_percent",
    )
    if any(not _valid_number(values.get(key), integer=True) for key in required_ints):
        raise RuntimeError("server resource telemetry snapshot has invalid integer fields")
    if any(not _valid_number(values.get(key)) for key in required_numbers):
        raise RuntimeError("server resource telemetry snapshot has invalid numeric fields")
    if any(not _valid_number(values.get(key), integer=True, optional=True) for key in optional_ints):
        raise RuntimeError("server resource telemetry snapshot has invalid optional integer fields")
    if any(not _valid_number(values.get(key), optional=True) for key in optional_numbers):
        raise RuntimeError("server resource telemetry snapshot has invalid optional numeric fields")


class RemoteResourceClient:
    """Read-only client for the optional AIOS-bench resource agent."""

    enabled = True
    source = "aios_bench_resource_agent"

    def __init__(self, url: str, *, timeout: float = 1.0) -> None:
        self.url = normalize_resource_url(url)
        self.timeout = max(0.1, float(timeout))

    @property
    def public_endpoint(self) -> str:
        return self.url

    def snapshot(self) -> ResourceSnapshot:
        headers = {"Accept": "application/json"}
        token = os.environ.get(TOKEN_ENV, "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(self.url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"server resource telemetry unavailable: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("schema") != RESOURCE_SCHEMA:
            raise RuntimeError("server resource telemetry returned an unsupported schema")
        if payload.get("target_alive") is not True:
            raise RuntimeError("server resource telemetry target process is not alive")
        raw = payload.get("snapshot")
        if not isinstance(raw, dict):
            raise RuntimeError("server resource telemetry returned an invalid snapshot")
        allowed = {field.name for field in fields(ResourceSnapshot)}
        values = {key: value for key, value in raw.items() if key in allowed}
        _validate_snapshot_values(values)
        try:
            return ResourceSnapshot(**values)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("server resource telemetry snapshot is incomplete") from exc


class NullRemoteResourceClient:
    enabled = False
    source = "unavailable"
    public_endpoint = None

    def snapshot(self) -> ResourceSnapshot:
        raise RuntimeError("server resource telemetry is disabled")


def build_remote_resource_client(url: str | None) -> RemoteResourceClient | NullRemoteResourceClient:
    configured = url or os.environ.get("AIOS_BENCH_SERVER_RESOURCE_URL")
    if not configured:
        return NullRemoteResourceClient()
    return RemoteResourceClient(configured)
