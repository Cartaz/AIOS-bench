from __future__ import annotations

import hmac
import json
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .black_box_service import (
    BlackBoxInputError,
    BlackBoxReferenceService,
    probe_log_path,
)
from .task_runtime import TaskRuntime


BLACK_BOX_BINDING_SCHEMA = "aios-bench/black-box-binding/v1"
MAX_REQUEST_BYTES = 32 * 1024


BLACK_BOX_CLIENT_SOURCE = '''\
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _binding() -> tuple[str, str]:
    endpoint = os.environ.get("AIOS_BENCH_BLACK_BOX_URL", "").strip()
    token = os.environ.get("AIOS_BENCH_BLACK_BOX_TOKEN", "").strip()
    if endpoint and token:
        return endpoint.rstrip("/"), token
    workspace = Path(os.environ.get("AIOS_BENCH_WORKSPACE", "."))
    path = workspace / "reference" / "api.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("black-box reference binding is unavailable") from exc
    endpoint = str(value.get("endpoint", "")).strip().rstrip("/")
    token = str(value.get("token", "")).strip()
    if not endpoint or not token:
        raise RuntimeError("black-box reference binding is incomplete")
    return endpoint, token


def _request(method: str, path: str, payload: dict | None = None) -> object:
    endpoint, token = _binding()
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(endpoint + path, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = {"error": "reference request failed"}
        print(json.dumps(detail, sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from exc
    except URLError as exc:
        print(json.dumps({"error": "reference API unavailable"}), file=sys.stderr)
        raise SystemExit(2) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="AIOS-Bench black-box reference client")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("contract", help="show public input/output contract and remaining probe budget")
    probe = commands.add_parser("probe", help="query one reference behavior input")
    probe.add_argument("--input", required=True, help="JSON object input")
    args = parser.parse_args()
    if args.command == "contract":
        result = _request("GET", "/v1/contract")
    else:
        try:
            payload = json.loads(args.input)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--input must be valid JSON: {exc}") from exc
        result = _request("POST", "/v1/probe", {"input": payload})
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
'''


class _BlackBoxHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _RuntimeOwner:
    def __init__(
        self,
        *,
        workspace: Path,
        run_dir: Path,
        task_id: str,
        oracle: Mapping[str, Any],
    ) -> None:
        self.workspace = workspace
        self.run_dir = run_dir
        self.task_id = task_id
        self.oracle = oracle
        self.binding_path = workspace / "reference" / "api.json"
        self.token = secrets.token_urlsafe(32)
        self.server: _BlackBoxHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._closed = False

    def start(self) -> TaskRuntime:
        spec = self.oracle.get("reference_spec")
        budget = self.oracle.get("probe_budget")
        if not isinstance(spec, Mapping) or not isinstance(budget, int):
            raise RuntimeError("black-box oracle is missing reference runtime data")
        log = probe_log_path(self.run_dir, self.task_id)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.unlink(missing_ok=True)
        service = BlackBoxReferenceService(spec, budget, log)
        handler = _handler_factory(service, self.token)
        self.server = _BlackBoxHTTPServer(("127.0.0.1", 0), handler)
        endpoint = f"http://127.0.0.1:{int(self.server.server_address[1])}"
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            name="aios-bench-black-box-api",
            daemon=True,
        )
        self.thread.start()
        self.binding_path.parent.mkdir(parents=True, exist_ok=True)
        self.binding_path.write_text(
            json.dumps(
                {
                    "schema": BLACK_BOX_BINDING_SCHEMA,
                    "endpoint": endpoint,
                    "token": self.token,
                    "client": "tools/reference_api.py",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return TaskRuntime(
            environment={
                "AIOS_BENCH_BLACK_BOX_URL": endpoint,
                "AIOS_BENCH_BLACK_BOX_TOKEN": self.token,
            },
            _closer=self.close,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        error: Exception | None = None
        if self.server is not None:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception as exc:
                error = exc
        if self.thread is not None:
            self.thread.join(timeout=5)
            if self.thread.is_alive() and error is None:
                error = RuntimeError("black-box reference API did not stop within shutdown bound")
        self.binding_path.unlink(missing_ok=True)
        if error is not None:
            raise error


def _handler_factory(
    service: BlackBoxReferenceService,
    token: str,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AIOSBenchBlackBoxAPI/1"
        sys_version = ""

        def log_message(self, format: str, *args: object) -> None:
            return

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization", "")
            prefix = "Bearer "
            candidate = header[len(prefix):] if header.startswith(prefix) else ""
            return bool(candidate) and hmac.compare_digest(candidate, token)

        def _send(self, status: HTTPStatus, payload: object) -> None:
            body = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _reject(self, status: HTTPStatus, message: str) -> None:
            self._send(status, {"error": message})

        def _auth(self) -> bool:
            if self._authorized():
                return True
            self._reject(HTTPStatus.UNAUTHORIZED, "valid bearer token required")
            return False

        def do_GET(self) -> None:
            if not self._auth():
                return
            if urlparse(self.path).path != "/v1/contract":
                self._reject(HTTPStatus.NOT_FOUND, "API route does not exist")
                return
            self._send(HTTPStatus.OK, service.contract())

        def do_POST(self) -> None:
            if not self._auth():
                return
            if urlparse(self.path).path != "/v1/probe":
                self._reject(HTTPStatus.NOT_FOUND, "API route does not exist")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_REQUEST_BYTES:
                    raise ValueError("request body size is invalid")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict) or set(payload) != {"input"}:
                    raise ValueError("probe requires exactly one input object")
                result = service.probe(payload["input"])
                self._send(HTTPStatus.OK, result)
            except BlackBoxInputError as exc:
                status = (
                    HTTPStatus.TOO_MANY_REQUESTS
                    if "budget exhausted" in str(exc)
                    else HTTPStatus.BAD_REQUEST
                )
                self._reject(status, str(exc))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                self._reject(HTTPStatus.BAD_REQUEST, str(exc))
            except Exception:
                self._reject(HTTPStatus.INTERNAL_SERVER_ERROR, "reference operation failed")

    return Handler


def write_black_box_client(workspace: Path) -> None:
    path = Path(workspace) / "tools" / "reference_api.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BLACK_BOX_CLIENT_SOURCE, encoding="utf-8")


def start_black_box_runtime(
    workspace: Path,
    run_dir: Path,
    task_id: str,
    oracle: Mapping[str, Any],
) -> TaskRuntime:
    owner = _RuntimeOwner(
        workspace=Path(workspace),
        run_dir=Path(run_dir),
        task_id=task_id,
        oracle=oracle,
    )
    return owner.start()


__all__ = [
    "BLACK_BOX_BINDING_SCHEMA",
    "start_black_box_runtime",
    "write_black_box_client",
]
