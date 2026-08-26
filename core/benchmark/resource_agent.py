from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psutil

from .remote_resources import RESOURCE_SCHEMA, TOKEN_ENV
from .resource_telemetry import LocalResourceProbe

logger = logging.getLogger(__name__)


class ResourceAgent:
    """Read-only resource snapshot service for an inference-server process tree."""

    def __init__(self, target_pid: int, *, token: str = "") -> None:
        if target_pid <= 0:
            raise ValueError("target PID must be positive")
        self.target_pid = target_pid
        self.token = token
        self.probe = LocalResourceProbe(root_pid=target_pid)

    def target_alive(self) -> bool:
        return psutil.pid_exists(self.target_pid)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_SCHEMA,
            "target_pid": self.target_pid,
            "target_alive": self.target_alive(),
            "snapshot": asdict(self.probe.snapshot()),
        }


class _ResourceHandler(BaseHTTPRequestHandler):
    server_version = "AIOSBenchResourceAgent/1"

    @property
    def agent(self) -> ResourceAgent:
        return self.server.resource_agent  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        path = self.path.partition("?")[0].rstrip("/") or "/"
        if path == "/health":
            self._json(
                HTTPStatus.OK,
                {
                    "schema": RESOURCE_SCHEMA,
                    "target_pid": self.agent.target_pid,
                    "target_alive": self.agent.target_alive(),
                },
            )
            return
        if path == "/v1/snapshot":
            self._json(HTTPStatus.OK, self.agent.snapshot_payload())
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _authorized(self) -> bool:
        if not self.agent.token:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {self.agent.token}"

    def _json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        logger.info("resource-agent %s", format % args)


class ResourceHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], agent: ResourceAgent) -> None:
        self.resource_agent = agent
        super().__init__(address, _ResourceHandler)


def serve_resource_agent(
    target_pid: int,
    *,
    bind: str = "127.0.0.1",
    port: int = 8766,
    token: str = "",
) -> None:
    agent = ResourceAgent(target_pid, token=token)
    if not agent.target_alive():
        raise RuntimeError(f"target PID {target_pid} is not running")
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if bind not in {"127.0.0.1", "::1", "localhost"} and not token:
        logger.warning("resource agent is exposed beyond loopback without bearer authentication")
    server = ResourceHTTPServer((bind, port), agent)
    logger.info("resource agent listening on %s:%d for PID %d", bind, port, target_pid)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="AIOS-bench read-only inference-server resource agent")
    parser.add_argument("--pid", type=int, required=True, help="PID of the inference server to observe")
    parser.add_argument("--bind", default="127.0.0.1", help="Listen address; loopback by default")
    parser.add_argument("--port", type=int, default=8766, help="Listen port")
    parser.add_argument(
        "--token-env",
        default=TOKEN_ENV,
        help="Environment variable containing the optional bearer token",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    token = os.environ.get(args.token_env, "").strip()
    serve_resource_agent(args.pid, bind=args.bind, port=args.port, token=token)


if __name__ == "__main__":
    main()
