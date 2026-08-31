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
from urllib.parse import unquote, urlparse

from .task_runtime import TaskRuntime
from .world_service import (
    API_CONTRACT_SCHEMA,
    SupportDependencyWorldService,
    SupportWorldService,
    WorldAPIError,
    world_action_log_path,
)


API_BINDING_SCHEMA = "aios-bench/world-api-binding/v1"
MAX_REQUEST_BYTES = 16 * 1024


WORLD_API_CLIENT_SOURCE = '''\
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _binding() -> tuple[str, str]:
    endpoint = os.environ.get("AIOS_BENCH_WORLD_API_URL", "").strip()
    token = os.environ.get("AIOS_BENCH_WORLD_API_TOKEN", "").strip()
    if endpoint and token:
        return endpoint.rstrip("/"), token
    workspace = Path(os.environ.get("AIOS_BENCH_WORKSPACE", "."))
    path = workspace / "world" / "api.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("world API binding is unavailable") from exc
    endpoint = str(value.get("endpoint", "")).strip().rstrip("/")
    token = str(value.get("token", "")).strip()
    if not endpoint or not token:
        raise RuntimeError("world API binding is incomplete")
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
            detail = {"error": {"code": "http_error", "message": "world API request failed"}}
        print(json.dumps(detail, sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from exc
    except URLError as exc:
        print('{"error":{"code":"unavailable","message":"world API is unavailable"}}', file=sys.stderr)
        raise SystemExit(2) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="AIOS-Bench world API client")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("schema", help="show available typed operations")
    commands.add_parser("list", help="list support tickets")
    get_parser = commands.add_parser("get", help="read one support ticket")
    get_parser.add_argument("ticket_id")
    account_parser = commands.add_parser("account", help="read one account profile")
    account_parser.add_argument("account_id")
    escalate = commands.add_parser("escalate", help="apply the escalation action to one ticket")
    escalate.add_argument("ticket_id")
    escalate.add_argument("--idempotency-key", required=True)
    args = parser.parse_args()

    if args.command == "schema":
        result = _request("GET", "/v1/schema")
    elif args.command == "list":
        result = _request("GET", "/v1/tickets")
    elif args.command == "get":
        result = _request("GET", f"/v1/tickets/{args.ticket_id}")
    elif args.command == "account":
        result = _request("GET", f"/v1/accounts/{args.account_id}")
    else:
        result = _request(
            "POST",
            "/v1/actions/escalate",
            {"ticket_id": args.ticket_id, "idempotency_key": args.idempotency_key},
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
'''


class _WorldHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _RuntimeOwner:
    def __init__(
        self,
        *,
        workspace_database: Path,
        hidden_database: Path,
        config_path: Path,
        action_log: Path,
        service_class: type[SupportWorldService],
    ) -> None:
        self.workspace_database = workspace_database
        self.hidden_database = hidden_database
        self.config_path = config_path
        self.action_log = action_log
        self.service_class = service_class
        self.token = secrets.token_urlsafe(32)
        self.service: SupportWorldService | None = None
        self.server: _WorldHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._closed = False

    def start(self) -> TaskRuntime:
        if not self.workspace_database.is_file():
            raise RuntimeError("stateful world database is missing before API startup")
        self.hidden_database.parent.mkdir(parents=True, exist_ok=True)
        self.hidden_database.unlink(missing_ok=True)
        self.action_log.unlink(missing_ok=True)
        shutil.move(str(self.workspace_database), str(self.hidden_database))
        try:
            self.service = self.service_class(self.hidden_database, self.action_log)
            handler = _handler_factory(self.service, self.token)
            self.server = _WorldHTTPServer(("127.0.0.1", 0), handler)
            port = int(self.server.server_address[1])
            endpoint = f"http://127.0.0.1:{port}"
            self.thread = threading.Thread(
                target=self.server.serve_forever,
                name="aios-bench-world-api",
                daemon=True,
            )
            self.thread.start()
            binding = {
                "schema": API_BINDING_SCHEMA,
                "endpoint": endpoint,
                "token": self.token,
                "client": "tools/world_api.py",
            }
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(binding, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return TaskRuntime(
                environment={
                    "AIOS_BENCH_WORLD_API_URL": endpoint,
                    "AIOS_BENCH_WORLD_API_TOKEN": self.token,
                },
                _closer=self.close,
            )
        except Exception:
            self._restore_database()
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
                    "world API server did not stop within shutdown bound"
                )
        try:
            self.config_path.unlink(missing_ok=True)
            self._restore_database()
        except Exception as exc:
            if close_error is None:
                close_error = exc
        if close_error is not None:
            raise close_error

    def _restore_database(self) -> None:
        if not self.hidden_database.is_file():
            return
        self.workspace_database.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.workspace_database.with_name(
            f".{self.workspace_database.name}.restore"
        )
        shutil.copy2(self.hidden_database, temporary)
        temporary.replace(self.workspace_database)
        self.hidden_database.unlink(missing_ok=True)


def _handler_factory(
    service: SupportWorldService,
    token: str,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AIOSBenchWorldAPI/1"
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

        def _error(self, error: WorldAPIError) -> None:
            self._send(
                error.status,
                {"error": {"code": error.code, "message": error.message}},
            )

        def _require_auth(self) -> bool:
            if self._authorized():
                return True
            self._error(
                WorldAPIError(
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
            try:
                if path == "/v1/schema":
                    self._send(HTTPStatus.OK, service.contract())
                    return
                if path == "/v1/tickets":
                    self._send(
                        HTTPStatus.OK,
                        {"tickets": service.list_tickets()},
                    )
                    return
                ticket_prefix = "/v1/tickets/"
                if path.startswith(ticket_prefix) and len(path) > len(ticket_prefix):
                    ticket_id = unquote(path[len(ticket_prefix):])
                    self._send(
                        HTTPStatus.OK,
                        {"ticket": service.get_ticket(ticket_id)},
                    )
                    return
                account_prefix = "/v1/accounts/"
                if path.startswith(account_prefix) and len(path) > len(account_prefix):
                    lookup = getattr(service, "get_account", None)
                    if lookup is None:
                        raise WorldAPIError(
                            HTTPStatus.NOT_FOUND,
                            "not_found",
                            "API route does not exist",
                        )
                    account_id = unquote(path[len(account_prefix):])
                    self._send(
                        HTTPStatus.OK,
                        {"account": lookup(account_id)},
                    )
                    return
                raise WorldAPIError(
                    HTTPStatus.NOT_FOUND,
                    "not_found",
                    "API route does not exist",
                )
            except WorldAPIError as exc:
                self._error(exc)
            except Exception:
                self._error(
                    WorldAPIError(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        "internal_error",
                        "world API operation failed",
                    )
                )

        def do_POST(self) -> None:
            if not self._require_auth():
                return
            path = urlparse(self.path).path
            try:
                if path != "/v1/actions/escalate":
                    raise WorldAPIError(
                        HTTPStatus.NOT_FOUND,
                        "not_found",
                        "API route does not exist",
                    )
                raw_length = self.headers.get("Content-Length", "")
                try:
                    length = int(raw_length)
                except ValueError as exc:
                    raise WorldAPIError(
                        HTTPStatus.BAD_REQUEST,
                        "invalid_request",
                        "Content-Length must be an integer",
                    ) from exc
                if length <= 0 or length > MAX_REQUEST_BYTES:
                    raise WorldAPIError(
                        HTTPStatus.BAD_REQUEST,
                        "invalid_request",
                        "request body size is invalid",
                    )
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise WorldAPIError(
                        HTTPStatus.BAD_REQUEST,
                        "invalid_json",
                        "request body must be valid UTF-8 JSON",
                    ) from exc
                if not isinstance(payload, dict) or set(payload) != {
                    "ticket_id",
                    "idempotency_key",
                }:
                    raise WorldAPIError(
                        HTTPStatus.BAD_REQUEST,
                        "invalid_schema",
                        "escalate action requires exactly ticket_id and idempotency_key",
                    )
                result = service.escalate_ticket(
                    payload["ticket_id"],
                    payload["idempotency_key"],
                )
                self._send(HTTPStatus.OK, result)
            except WorldAPIError as exc:
                self._error(exc)
            except Exception:
                self._error(
                    WorldAPIError(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        "internal_error",
                        "world API operation failed",
                    )
                )

    return Handler


def write_world_api_client(workspace: Path) -> None:
    path = Path(workspace) / "tools" / "world_api.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(WORLD_API_CLIENT_SOURCE, encoding="utf-8")


def _start_world_runtime(
    workspace: Path,
    run_dir: Path,
    task_id: str,
    oracle: Mapping[str, Any],
    *,
    service_class: type[SupportWorldService],
) -> TaskRuntime:
    interface = oracle.get("mutation_interface")
    if not isinstance(interface, Mapping) or interface.get("schema") != API_CONTRACT_SCHEMA:
        return TaskRuntime()
    relative = str(oracle.get("database_path", ""))
    if not relative:
        raise RuntimeError("stateful world oracle has no database path")
    workspace_database = Path(workspace) / relative
    hidden_root = Path(run_dir) / "world_api"
    owner = _RuntimeOwner(
        workspace_database=workspace_database,
        hidden_database=hidden_root / f"{task_id}.db",
        config_path=Path(workspace) / "world" / "api.json",
        action_log=world_action_log_path(run_dir, task_id),
        service_class=service_class,
    )
    return owner.start()


def start_support_world_runtime(
    workspace: Path,
    run_dir: Path,
    task_id: str,
    oracle: Mapping[str, Any],
) -> TaskRuntime:
    return _start_world_runtime(
        workspace,
        run_dir,
        task_id,
        oracle,
        service_class=SupportWorldService,
    )


def start_dependency_world_runtime(
    workspace: Path,
    run_dir: Path,
    task_id: str,
    oracle: Mapping[str, Any],
) -> TaskRuntime:
    return _start_world_runtime(
        workspace,
        run_dir,
        task_id,
        oracle,
        service_class=SupportDependencyWorldService,
    )
