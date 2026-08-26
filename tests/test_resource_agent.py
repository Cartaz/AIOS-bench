from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request

import pytest

from core.benchmark.remote_resources import RESOURCE_SCHEMA
from core.benchmark.resource_agent import ResourceAgent, ResourceHTTPServer
from core.benchmark.resource_telemetry import ResourceSnapshot


def _snapshot() -> ResourceSnapshot:
    return ResourceSnapshot(
        captured_at=10.0,
        process_rss_bytes=100,
        process_cpu_percent=5.0,
        process_count=1,
        host_cpu_percent=15.0,
        host_ram_used_bytes=1000,
    )


class FakeProbe:
    def snapshot(self) -> ResourceSnapshot:
        return _snapshot()


def _start_server(agent: ResourceAgent):
    server = ResourceHTTPServer(("127.0.0.1", 0), agent)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_resource_agent_snapshot_endpoint_is_read_only_and_schema_versioned():
    agent = ResourceAgent(os.getpid())
    agent.probe = FakeProbe()
    server, thread = _start_server(agent)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/v1/snapshot",
            timeout=2,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["schema"] == RESOURCE_SCHEMA
        assert payload["target_alive"] is True
        assert payload["snapshot"]["process_rss_bytes"] == 100
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_resource_agent_bearer_token_protects_lan_endpoint():
    agent = ResourceAgent(os.getpid(), token="secret")
    agent.probe = FakeProbe()
    server, thread = _start_server(agent)
    url = f"http://127.0.0.1:{server.server_port}/v1/snapshot"
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(url, timeout=2)
        assert exc.value.code == 401

        request = urllib.request.Request(
            url,
            headers={"Authorization": "Bearer secret"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["snapshot"]["host_ram_used_bytes"] == 1000
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
