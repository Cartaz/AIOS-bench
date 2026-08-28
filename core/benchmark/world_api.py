from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlparse

from .task_runtime import TaskRuntime


ACTION_LOG_SCHEMA = "aios-bench/world-api-action/v1"
API_BINDING_SCHEMA = "aios-bench/world-api-binding/v1"
API_CONTRACT_SCHEMA = "aios-bench/world-api-contract/v1"
MAX_REQUEST_BYTES = 16 * 1024
_TICKET_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


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


class WorldAPIError(Exception):
    def __init__(self, status: HTTPStatus, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class SupportWorldService:
    """Narrow domain service over a generated support-world database."""

    def __init__(self, database: Path, action_log: Path) -> None:
        self.database = Path(database)
        self.action_log = Path(action_log)
        self.action_log.parent.mkdir(parents=True, exist_ok=True)
        self.action_log.unlink(missing_ok=True)
        self._lock = threading.RLock()
        self._sequence = 0
        self._idempotency: dict[str, tuple[tuple[str, str], dict[str, Any]]] = {}

    @staticmethod
    def contract() -> dict[str, Any]:
        return {
            "schema": API_CONTRACT_SCHEMA,
            "read_operations": {
                "list_tickets": {"method": "GET", "path": "/v1/tickets"},
                "get_ticket": {
                    "method": "GET",
                    "path": "/v1/tickets/{ticket_id}",
                    "ticket_id": "string[1..128]",
                },
            },
            "write_operations": {
                "escalate_ticket": {
                    "method": "POST",
                    "path": "/v1/actions/escalate",
                    "body": {
                        "ticket_id": "string[1..128]",
                        "idempotency_key": "string[1..128]",
                    },
                    "effect": {
                        "priority": "urgent",
                        "assignee": "oncall",
                        "escalation_reason": "policy_match",
                    },
                }
            },
            "idempotency": "same key and same action replays the original result; key reuse for another action is rejected",
        }

    @staticmethod
    def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {key: row[key] for key in row.keys()}

    def list_tickets(self) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.database) as connection:
            connection.row_factory = sqlite3.Row
            return [
                self._row_dict(row)
                for row in connection.execute("SELECT * FROM tickets ORDER BY id")
            ]

    def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        ticket_id = self._validate_ticket_id(ticket_id)
        with self._lock, sqlite3.connect(self.database) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM tickets WHERE id = ?",
                (ticket_id,),
            ).fetchone()
            if row is None:
                raise WorldAPIError(HTTPStatus.NOT_FOUND, "ticket_not_found", "ticket does not exist")
            return self._row_dict(row)

    def escalate_ticket(self, ticket_id: str, idempotency_key: str) -> dict[str, Any]:
        ticket_id = self._validate_ticket_id(ticket_id)
        idempotency_key = self._validate_idempotency_key(idempotency_key)
        fingerprint = ("escalate_ticket", ticket_id)
        with self._lock:
            previous = self._idempotency.get(idempotency_key)
            if previous is not None:
                if previous[0] != fingerprint:
                    raise WorldAPIError(
                        HTTPStatus.CONFLICT,
                        "idempotency_conflict",
                        "idempotency key was already used for another action",
                    )
                replay = dict(previous[1])
                replay["idempotent_replay"] = True
                return replay

            with sqlite3.connect(self.database) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute(
                    "SELECT * FROM tickets WHERE id = ?",
                    (ticket_id,),
                ).fetchone()
                if row is None:
                    raise WorldAPIError(
                        HTTPStatus.NOT_FOUND,
                        "ticket_not_found",
                        "ticket does not exist",
                    )
                before = self._row_dict(row)
                changed = not (
                    before["priority"] == "urgent"
                    and before["assignee"] == "oncall"
                    and before["escalation_reason"] == "policy_match"
                )
                if changed:
                    connection.execute(
                        """
                        UPDATE tickets
                        SET priority = 'urgent', assignee = 'oncall', escalation_reason = 'policy_match'
                        WHERE id = ?
                        """,
                        (ticket_id,),
                    )
                    connection.commit()
                after_row = connection.execute(
                    "SELECT * FROM tickets WHERE id = ?",
                    (ticket_id,),
                ).fetchone()
                if after_row is None:
                    raise RuntimeError("ticket disappeared during world mutation")
                after = self._row_dict(after_row)

            response = {
                "operation": "escalate_ticket",
                "ticket_id": ticket_id,
                "changed": changed,
                "idempotent_replay": False,
                "state": after,
            }
            self._append_action(
                {
                    "schema": ACTION_LOG_SCHEMA,
                    "operation": "escalate_ticket",
                    "idempotency_key": idempotency_key,
                    "ticket_id": ticket_id,
                    "outcome": "applied" if changed else "already_applied",
                    "changed": changed,
                    "before": before,
                    "after": after,
                }
            )
            self._idempotency[idempotency_key] = (fingerprint, dict(response))
            return response

    @staticmethod
    def _validate_ticket_id(value: object) -> str:
        if not isinstance(value, str) or _TICKET_ID.fullmatch(value) is None:
            raise WorldAPIError(
                HTTPStatus.BAD_REQUEST,
                "invalid_ticket_id",
                "ticket_id must be a non-empty identifier up to 128 characters",
            )
        return value

    @staticmethod
    def _validate_idempotency_key(value: object) -> str:
        if not isinstance(value, str) or _IDEMPOTENCY_KEY.fullmatch(value) is None:
            raise WorldAPIError(
                HTTPStatus.BAD_REQUEST,
                "invalid_idempotency_key",
                "idempotency_key must use identifier characters and be at most 128 characters",
            )
        return value

    def _append_action(self, record: dict[str, Any]) -> None:
        self._sequence += 1
        payload = {"sequence": self._sequence, **record}
        with self.action_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


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
    ) -> None:
        self.workspace_database = workspace_database
        self.hidden_database = hidden_database
        self.config_path = config_path
        self.action_log = action_log
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
            self.service = SupportWorldService(self.hidden_database, self.action_log)
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
                close_error = RuntimeError("world API server did not stop within shutdown bound")
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
        temporary = self.workspace_database.with_name(f".{self.workspace_database.name}.restore")
        shutil.copy2(self.hidden_database, temporary)
        temporary.replace(self.workspace_database)
        self.hidden_database.unlink(missing_ok=True)


def _handler_factory(service: SupportWorldService, token: str) -> type[BaseHTTPRequestHandler]:
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
            body = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
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
                    self._send(HTTPStatus.OK, {"tickets": service.list_tickets()})
                    return
                prefix = "/v1/tickets/"
                if path.startswith(prefix) and len(path) > len(prefix):
                    ticket_id = unquote(path[len(prefix):])
                    self._send(HTTPStatus.OK, {"ticket": service.get_ticket(ticket_id)})
                    return
                raise WorldAPIError(HTTPStatus.NOT_FOUND, "not_found", "API route does not exist")
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
                    raise WorldAPIError(HTTPStatus.NOT_FOUND, "not_found", "API route does not exist")
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


def world_action_log_path(run_dir: Path, task_id: str) -> Path:
    return Path(run_dir) / "world_api" / f"{task_id}.jsonl"


def write_world_api_client(workspace: Path) -> None:
    path = Path(workspace) / "tools" / "world_api.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(WORLD_API_CLIENT_SOURCE, encoding="utf-8")


def start_support_world_runtime(
    workspace: Path,
    run_dir: Path,
    task_id: str,
    oracle: Mapping[str, Any],
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
    )
    return owner.start()


def load_world_action_log(run_dir: Path, task_id: str) -> list[dict[str, Any]]:
    path = world_action_log_path(run_dir, task_id)
    if not path.is_file():
        raise FileNotFoundError(path)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid world API action log JSON at line {line_number}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"invalid world API action log record at line {line_number}")
        records.append(item)
    return records


def verify_support_action_log(
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None,
    task_id: str | None,
) -> tuple[bool, str]:
    interface = oracle.get("mutation_interface")
    if not isinstance(interface, Mapping) or interface.get("schema") != API_CONTRACT_SCHEMA:
        return True, "world API provenance not required"
    if run_dir is None or not task_id:
        return False, "world API action log context is unavailable"
    try:
        records = load_world_action_log(run_dir, task_id)
    except (FileNotFoundError, OSError, ValueError) as exc:
        return False, f"world API action log unavailable: {type(exc).__name__}"

    baseline = {
        str(row.get("id")): dict(row)
        for row in (oracle.get("baseline_rows") or [])
        if isinstance(row, Mapping) and row.get("id") is not None
    }
    targets = {str(value) for value in (oracle.get("target_ids") or [])}
    expected_mutations = oracle.get("expected_mutations") or {}
    applied: set[str] = set()

    for expected_sequence, record in enumerate(records, 1):
        if record.get("schema") != ACTION_LOG_SCHEMA:
            return False, "world API action log schema mismatch"
        if record.get("sequence") != expected_sequence:
            return False, "world API action log sequence is not contiguous"
        if record.get("operation") != "escalate_ticket":
            return False, "unexpected world API write operation"
        if not record.get("changed"):
            continue
        ticket_id = str(record.get("ticket_id", ""))
        if ticket_id not in targets:
            return False, f"world API changed non-target ticket: {ticket_id}"
        if ticket_id in applied:
            return False, f"world API changed target more than once: {ticket_id}"
        before = record.get("before")
        if before != baseline.get(ticket_id):
            return False, f"target was modified before world API action: {ticket_id}"
        mutation = expected_mutations.get(ticket_id)
        if not isinstance(mutation, Mapping):
            return False, f"missing expected world API mutation: {ticket_id}"
        expected_after = dict(baseline[ticket_id])
        expected_after.update(dict(mutation))
        if record.get("after") != expected_after:
            return False, f"world API action produced unexpected state: {ticket_id}"
        applied.add(ticket_id)

    missing = sorted(targets - applied)
    if missing:
        return False, f"required world API mutations missing: {', '.join(missing)}"
    return True, "world API action provenance verified"
