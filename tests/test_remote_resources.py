from __future__ import annotations

import json
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from core.benchmark.remote_resources import (
    RESOURCE_SCHEMA,
    RemoteResourceClient,
    normalize_resource_url,
)
from core.benchmark.resource_telemetry import ResourceSnapshot


def _snapshot() -> ResourceSnapshot:
    return ResourceSnapshot(
        captured_at=12.5,
        process_rss_bytes=1024,
        process_cpu_percent=25.0,
        process_count=2,
        host_cpu_percent=40.0,
        host_ram_used_bytes=4096,
        process_gpu_engine_time_percent=18.0,
        process_vram_used_bytes=2048,
        process_gpu_client_count=1,
        gpu_busy_percent=55.0,
        vram_used_bytes=3072,
        vram_total_bytes=8192,
        gpu_device_count=1,
    )


def test_normalize_resource_url_defaults_to_snapshot_endpoint():
    assert normalize_resource_url("192.0.2.10:8766") == "http://192.0.2.10:8766/v1/snapshot"
    assert normalize_resource_url("https://example.test/telemetry") == (
        "https://example.test/telemetry/v1/snapshot"
    )


def test_remote_client_reads_valid_snapshot(monkeypatch):
    payload = json.dumps({
        "schema": RESOURCE_SCHEMA,
        "target_alive": True,
        "snapshot": asdict(_snapshot()),
    }).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = RemoteResourceClient(f"http://127.0.0.1:{server.server_port}")
        assert client.snapshot() == _snapshot()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_remote_client_rejects_malformed_numeric_types(monkeypatch):
    payload = {
        "schema": RESOURCE_SCHEMA,
        "target_alive": True,
        "snapshot": asdict(_snapshot()),
    }
    payload["snapshot"]["process_rss_bytes"] = "1024"

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(RuntimeError, match="invalid integer fields"):
        RemoteResourceClient("http://server.test").snapshot()


def test_remote_client_rejects_dead_target(monkeypatch):
    payload = {
        "schema": RESOURCE_SCHEMA,
        "target_alive": False,
        "snapshot": asdict(_snapshot()),
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(RuntimeError, match="target process is not alive"):
        RemoteResourceClient("http://server.test").snapshot()
