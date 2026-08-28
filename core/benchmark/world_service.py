from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from http import HTTPStatus
from pathlib import Path
from typing import Any, Mapping


ACTION_LOG_SCHEMA = "aios-bench/world-api-action/v1"
API_CONTRACT_SCHEMA = "aios-bench/world-api-contract/v1"
_TICKET_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


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
            "idempotency": (
                "same key and same action replays the original result; "
                "key reuse for another action is rejected"
            ),
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
                raise WorldAPIError(
                    HTTPStatus.NOT_FOUND,
                    "ticket_not_found",
                    "ticket does not exist",
                )
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


def world_action_log_path(run_dir: Path, task_id: str) -> Path:
    return Path(run_dir) / "world_api" / f"{task_id}.jsonl"


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
            raise ValueError(
                f"invalid world API action log JSON at line {line_number}"
            ) from exc
        if not isinstance(item, dict):
            raise ValueError(
                f"invalid world API action log record at line {line_number}"
            )
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
