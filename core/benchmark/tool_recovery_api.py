from __future__ import annotations

import hmac
import json
import secrets
import shutil
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .task_runtime import TaskRuntime
from .tool_recovery_service import (
    ToolRecoveryError,
    ToolRecoveryService,
    tool_action_log_path,
)


TOOL_BINDING_SCHEMA = "aios-bench/tool-recovery-binding/v1"
MAX_REQUEST_BYTES = 16 * 1024


TOOL_CLIENT_SOURCE = '''\
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _binding() -> tuple[str, str]:
    endpoint = os.environ.get("AIOS_BENCH_TOOL_API_URL", "").strip()
    token = os.environ.get("AIOS_BENCH_TOOL_API_TOKEN", "").strip()
    if endpoint and token:
        return endpoint.rstrip("/"), token
    workspace = Path(os.environ.get("AIOS_BENCH_WORKSPACE", "."))
    path = workspace / "tool" / "api.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("tool API binding is unavailable") from exc
    endpoint = str(value.get("endpoint", "")).strip().rstrip("/")
    token = str(value.get("token", "")).strip()
    if not endpoint or not token:
        raise RuntimeError("tool API binding is incomplete")
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
            detail = {
                "error": {
                    "code": "http_error",
                    "message": "tool request failed",
                    "retryable": False,
                }
            }
        print(json.dumps(detail, sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from exc
    except URLError as exc:
        print(
            '{"error":{"code":"unavailable","message":"tool API is unavailable","retryable":true}}',
            file=sys.stderr,
        )
        raise SystemExit(2) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="AIOS-Bench typed tool client")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("schema", help="show the complete typed tool schema")
    invoke = commands.add_parser("invoke", help="invoke one exact tool by name")
    invoke.add_argument("tool")
    invoke.add_argument("--args", default="{}", help="JSON object containing typed arguments")
    args = parser.parse_args()

    if args.command == "schema":
        result = _request("GET", "/v1/schema")
    else:
        try:
            arguments = json.loads(args.args)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--args must be valid JSON: {exc}") from exc
        result = _request(
            "POST",
            "/v1/invoke",
            {"tool": args.tool, "arguments": arguments},
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
'''


class _ToolHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _RuntimeOwner:
    def __init__(
        self,
        *,
        workspace_state: Path,
        hidden_state: Path,
        config_path: Path,
        action_log: Path,
        oracle: Mapping[str, Any],
    ) -> None:
        self.workspace_state = workspace_state
        self.hidden_state = hidden_state
        self.config_path = config_path
        self.action_log = action_log
        self.oracle = oracle
        self.token = secrets.token_urlsafe(32)
        self.service: ToolRecoveryService | None = None
        self.server: _ToolHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._closed = False

    def start(self) -> TaskRuntime:
        if not self.workspace_state.is_file():
            raise RuntimeError("tool recovery state is missing before API startup")
        self.hidden_state.parent.mkdir(parents=True, exist_ok=True)
        self.hidden_state.unlink(missing_ok=True)
        self.action_log.unlink(missing_ok=True)
        shutil.move(str(self.workspace_state), str(self.hidden_state))
        try:
            self.service = ToolRecoveryService(
                self.hidden_state,
                self.action_log,
                self.oracle,
            )
            handler = _handler_factory(self.service, self.token)
            self.server = _ToolHTTPServer(("127.0.0.1", 0), handler)
            endpoint = f"http://127.0.0.1:{int(self.server.server_address[1])}"
            self.thread = threading.Thread(
                target=self.server.serve_forever,
                name="aios-bench-tool-recovery-api",
                daemon=True,
            )
            self.thread.start()
            binding = {
                "schema": TOOL_BINDING_SCHEMA,
                "endpoint": endpoint,
                "token": self.token,
                "client": "tools/tool_api.py",
            }
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(binding, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return TaskRuntime(
                environment={
                    "AIOS_BENCH_TOOL_API_URL": endpoint,
                    "AIOS_BENCH_TOOL_API_TOKEN": self.token,
                },
                _closer=self.close,
            )
        except Exception:
            self._restore_state()
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close_error: Exception | None = None
        if self.server is not None:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception as exc:
                close_error = exc
        if self.thread is not None:
            self.thread.join(timeout=5)
            if self.thread.is_alive() and close_error is None:
                close_error = RuntimeError(
                    "tool recovery API server did not stop within shutdown bound"
                )
        try:
            self.config_path.unlink(missing_ok=True)
            self._restore_state()
        except Exception as exc:
            if close_error is None:
                close_error = exc
        if close_error is not None:
            raise close_error

    def _restore_state(self) -> None:
        if not self.hidden_state.is_file():
            return
        self.workspace_state.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.workspace_state.with_name(f".{self.workspace_state.name}.restore")
        shutil.copy2(self.hidden_state, temporary)
        temporary.replace(self.workspace_state)
        self.hidden_state.unlink(missing_ok=True)


def _handler_factory(
    service: ToolRecoveryService,
    token: str,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AIOSBenchToolRecoveryAPI/1"
        sys_version = ""

        def log_message(self, format: str, *args: object) -> None:
            return

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization", "")
            prefix = "Bearer "
            candidate = header[len(prefix):] if header.startswith(prefix) else ""
            return bool(candidate) and hmac.compare_digest(candidate, token)

        def _send(self, status: HTTPStatus, payload: object) -> None:
            body = json.dumps(
                payload,
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _error(self, error: ToolRecoveryError) -> None:
            self._send(
                error.status,
                {
                    "error": {
                        "code": error.code,
                        "message": error.message,
                        "retryable": error.retryable,
                    }
                },
            )

        def _require_auth(self) -> bool:
            if self._authorized():
                return True
            self._error(
                ToolRecoveryError(
                    HTTPStatus.UNAUTHORIZED,
                    "unauthorized",
                    "valid bearer token required",
                )
            )
            return False

        def do_GET(self) -> None:
            if not self._require_auth():
                return
            path = urlparse(self.path).path
            if path != "/v1/schema":
                self._error(
                    ToolRecoveryError(
                        HTTPStatus.NOT_FOUND,
                        "not_found",
                        "API route does not exist",
                    )
                )
                return
            self._send(HTTPStatus.OK, service.contract())

        def do_POST(self) -> None:
            if not self._require_auth():
                return
            if urlparse(self.path).path != "/v1/invoke":
                self._error(
                    ToolRecoveryError(
                        HTTPStatus.NOT_FOUND,
                        "not_found",
                        "API route does not exist",
                    )
                )
                return
            try:
                raw_length = self.headers.get("Content-Length", "")
                try:
                    length = int(raw_length)
                except ValueError as exc:
                    raise ToolRecoveryError(
                        HTTPStatus.BAD_REQUEST,
                        "invalid_request",
                        "Content-Length must be an integer",
                    ) from exc
                if length <= 0 or length > MAX_REQUEST_BYTES:
                    raise ToolRecoveryError(
                        HTTPStatus.BAD_REQUEST,
                        "invalid_request",
                        "request body size is invalid",
                    )
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ToolRecoveryError(
                        HTTPStatus.BAD_REQUEST,
                        "invalid_json",
                        "request body must be valid UTF-8 JSON",
                    ) from exc
                if not isinstance(payload, dict) or set(payload) != {"tool", "arguments"}:
                    raise ToolRecoveryError(
                        HTTPStatus.BAD_REQUEST,
                        "invalid_request",
                        "invoke requires exactly tool and arguments",
                    )
                result = service.invoke(payload["tool"], payload["arguments"])
                self._send(HTTPStatus.OK, result)
            except ToolRecoveryError as exc:
                self._error(exc)
            except Exception:
                self._error(
                    ToolRecoveryError(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        "internal_error",
                        "tool operation failed",
                    )
                )

    return Handler


def write_tool_recovery_client(workspace: Path) -> None:
    path = Path(workspace) / "tools" / "tool_api.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TOOL_CLIENT_SOURCE, encoding="utf-8")


def start_tool_recovery_runtime(
    workspace: Path,
    run_dir: Path,
    task_id: str,
    oracle: Mapping[str, Any],
) -> TaskRuntime:
    relative = str(oracle.get("state_path", ""))
    if not relative:
        raise RuntimeError("tool recovery oracle has no state path")
    owner = _RuntimeOwner(
        workspace_state=Path(workspace) / relative,
        hidden_state=Path(run_dir) / "tool_recovery" / f"{task_id}.state.json",
        config_path=Path(workspace) / "tool" / "api.json",
        action_log=tool_action_log_path(run_dir, task_id),
        oracle=oracle,
    )
    return owner.start()


__all__ = [
    "TOOL_BINDING_SCHEMA",
    "start_tool_recovery_runtime",
    "write_tool_recovery_client",
]
