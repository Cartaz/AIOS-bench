from __future__ import annotations

import json
import os
import re
import threading
from http import HTTPStatus
from pathlib import Path
from typing import Any, Mapping


TOOL_ACTION_LOG_SCHEMA = "aios-bench/tool-recovery-action/v1"
TOOL_CONTRACT_SCHEMA = "aios-bench/tool-recovery-contract/v1"
_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class ToolRecoveryError(Exception):
    def __init__(
        self,
        status: HTTPStatus,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable


class ToolRecoveryService:
    """Deterministic typed-tool surface with observable recovery hazards."""

    ACTIVE_TOOLS = ("cases.list", "cases.get", "actions.process")

    def __init__(
        self,
        state_path: Path,
        action_log: Path,
        oracle: Mapping[str, Any],
    ) -> None:
        self.state_path = Path(state_path)
        self.action_log = Path(action_log)
        self.action_log.parent.mkdir(parents=True, exist_ok=True)
        self.action_log.unlink(missing_ok=True)
        self.oracle = oracle
        self._lock = threading.RLock()
        self._sequence = 0
        self._read_attempts: dict[str, int] = {}
        self._idempotency: dict[str, tuple[str, dict[str, Any]]] = {}
        self._incomplete = {str(value) for value in oracle.get("incomplete_case_ids") or []}
        self._read_transients = {
            str(value) for value in oracle.get("transient_read_case_ids") or []
        }
        self._ambiguous_writes = {
            str(value) for value in oracle.get("ambiguous_write_case_ids") or []
        }
        self._distractor_tools = tuple(
            str(value) for value in oracle.get("distractor_tool_names") or []
        )

    def contract(self) -> dict[str, Any]:
        tools: list[dict[str, Any]] = [
            {
                "name": "cases.list",
                "lifecycle": "active",
                "arguments": {},
                "description": (
                    "List current cases. Rows marked complete=false omit decision fields and "
                    "must be resolved with cases.get."
                ),
            },
            {
                "name": "cases.get",
                "lifecycle": "active",
                "arguments": {"case_id": "string[1..128]"},
                "description": "Read one current case by exact id.",
            },
            {
                "name": "actions.process",
                "lifecycle": "active",
                "arguments": {
                    "case_id": "string[1..128]",
                    "idempotency_key": "string[1..128]",
                },
                "description": (
                    "Apply the process action. Retryable response_lost errors may happen after "
                    "the write commits; retry the identical action with the same idempotency key."
                ),
            },
        ]
        for name in self._distractor_tools:
            tools.append(
                {
                    "name": name,
                    "lifecycle": "legacy",
                    "arguments": {"case_id": "string[1..128]"},
                    "description": "Compatibility-only historical tool; not valid for current workflows.",
                }
            )
        return {
            "schema": TOOL_CONTRACT_SCHEMA,
            "tools": tools,
            "error_contract": {
                "retryable": "retry only when true",
                "response_lost": (
                    "write may already have committed; replay the identical request with the same key"
                ),
                "invalid_schema": "correct arguments instead of blind retry",
            },
        }

    def invoke(self, tool: object, arguments: object) -> object:
        if not isinstance(tool, str) or not tool:
            self._append(
                tool=str(tool),
                outcome="schema_error",
                code="invalid_tool_name",
                retryable=False,
            )
            raise ToolRecoveryError(
                HTTPStatus.BAD_REQUEST,
                "invalid_tool_name",
                "tool must be a non-empty string",
            )
        if not isinstance(arguments, dict):
            self._append(
                tool=tool,
                outcome="schema_error",
                code="invalid_schema",
                retryable=False,
            )
            raise ToolRecoveryError(
                HTTPStatus.BAD_REQUEST,
                "invalid_schema",
                "arguments must be a JSON object",
            )

        if tool in self._distractor_tools:
            self._append(
                tool=tool,
                outcome="distractor",
                code="inactive_tool",
                retryable=False,
            )
            raise ToolRecoveryError(
                HTTPStatus.GONE,
                "inactive_tool",
                "tool is not active for the current workflow",
            )
        if tool == "cases.list":
            self._require_keys(tool, arguments, set())
            result = self._list_cases()
            self._append(tool=tool, outcome="success", retryable=False)
            return result
        if tool == "cases.get":
            self._require_keys(tool, arguments, {"case_id"})
            case_id = self._identifier(arguments["case_id"], "case_id")
            return self._get_case(case_id)
        if tool == "actions.process":
            self._require_keys(tool, arguments, {"case_id", "idempotency_key"})
            case_id = self._identifier(arguments["case_id"], "case_id")
            key = self._identifier(arguments["idempotency_key"], "idempotency_key")
            return self._process(case_id, key)

        self._append(
            tool=tool,
            outcome="distractor",
            code="unknown_tool",
            retryable=False,
        )
        raise ToolRecoveryError(
            HTTPStatus.NOT_FOUND,
            "unknown_tool",
            "tool does not exist",
        )

    def _require_keys(self, tool: str, arguments: Mapping[str, Any], expected: set[str]) -> None:
        if set(arguments) == expected:
            return
        self._append(
            tool=tool,
            outcome="schema_error",
            code="invalid_schema",
            retryable=False,
            argument_keys=sorted(str(key) for key in arguments),
        )
        raise ToolRecoveryError(
            HTTPStatus.BAD_REQUEST,
            "invalid_schema",
            f"{tool} requires exactly: {', '.join(sorted(expected)) or 'no arguments'}",
        )

    def _identifier(self, value: object, label: str) -> str:
        if not isinstance(value, str) or _ID.fullmatch(value) is None:
            raise ToolRecoveryError(
                HTTPStatus.BAD_REQUEST,
                "invalid_schema",
                f"{label} must use identifier characters and be at most 128 characters",
            )
        return value

    def _load_state(self) -> dict[str, Any]:
        value = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
            raise RuntimeError("tool recovery state is malformed")
        return value

    def _save_state(self, state: Mapping[str, Any]) -> None:
        temporary = self.state_path.with_name(f".{self.state_path.name}.tmp")
        temporary.write_text(
            json.dumps(dict(state), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    def _case(self, state: Mapping[str, Any], case_id: str) -> dict[str, Any]:
        for item in state.get("cases") or []:
            if isinstance(item, dict) and str(item.get("id")) == case_id:
                return item
        raise ToolRecoveryError(
            HTTPStatus.NOT_FOUND,
            "case_not_found",
            "case does not exist",
        )

    def _list_cases(self) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            rows: list[dict[str, Any]] = []
            for raw in sorted(
                (item for item in state["cases"] if isinstance(item, dict)),
                key=lambda item: str(item.get("id")),
            ):
                case_id = str(raw["id"])
                if case_id in self._incomplete:
                    rows.append(
                        {
                            "id": case_id,
                            "status": raw["status"],
                            "complete": False,
                        }
                    )
                else:
                    rows.append(
                        {
                            "id": case_id,
                            "status": raw["status"],
                            "priority": raw["priority"],
                            "region": raw["region"],
                            "complete": True,
                        }
                    )
            return {"cases": rows}

    def _get_case(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            attempt = self._read_attempts.get(case_id, 0) + 1
            self._read_attempts[case_id] = attempt
            if case_id in self._read_transients and attempt == 1:
                self._append(
                    tool="cases.get",
                    outcome="transient_failure",
                    code="backend_busy",
                    retryable=True,
                    case_id=case_id,
                    attempt=attempt,
                )
                raise ToolRecoveryError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "backend_busy",
                    "temporary backend failure",
                    retryable=True,
                )
            state = self._load_state()
            row = dict(self._case(state, case_id))
            self._append(
                tool="cases.get",
                outcome="success",
                retryable=False,
                case_id=case_id,
                attempt=attempt,
            )
            return {"case": row}

    def _process(self, case_id: str, idempotency_key: str) -> dict[str, Any]:
        with self._lock:
            previous = self._idempotency.get(idempotency_key)
            if previous is not None:
                if previous[0] != case_id:
                    self._append(
                        tool="actions.process",
                        outcome="schema_error",
                        code="idempotency_conflict",
                        retryable=False,
                        case_id=case_id,
                        idempotency_key=idempotency_key,
                    )
                    raise ToolRecoveryError(
                        HTTPStatus.CONFLICT,
                        "idempotency_conflict",
                        "idempotency key was already used for another case",
                    )
                replay = dict(previous[1])
                replay["idempotent_replay"] = True
                self._append(
                    tool="actions.process",
                    outcome="idempotent_replay",
                    retryable=False,
                    case_id=case_id,
                    idempotency_key=idempotency_key,
                )
                return replay

            state = self._load_state()
            row = self._case(state, case_id)
            before_count = int(row.get("process_count", 0))
            row["processed"] = True
            row["process_count"] = before_count + 1
            self._save_state(state)
            response = {
                "case_id": case_id,
                "processed": True,
                "process_count": row["process_count"],
                "idempotent_replay": False,
            }
            self._idempotency[idempotency_key] = (case_id, dict(response))

            if case_id in self._ambiguous_writes and before_count == 0:
                self._append(
                    tool="actions.process",
                    outcome="applied_response_lost",
                    code="response_lost",
                    retryable=True,
                    case_id=case_id,
                    idempotency_key=idempotency_key,
                    changed=True,
                )
                raise ToolRecoveryError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "response_lost",
                    "response was lost after the write committed",
                    retryable=True,
                )

            self._append(
                tool="actions.process",
                outcome="applied" if before_count == 0 else "duplicate_applied",
                retryable=False,
                case_id=case_id,
                idempotency_key=idempotency_key,
                changed=True,
            )
            return response

    def _append(self, *, tool: str, outcome: str, retryable: bool, **extra: Any) -> None:
        self._sequence += 1
        record = {
            "schema": TOOL_ACTION_LOG_SCHEMA,
            "sequence": self._sequence,
            "tool": tool,
            "outcome": outcome,
            "retryable": bool(retryable),
            **extra,
        }
        with self.action_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def tool_action_log_path(run_dir: Path, task_id: str) -> Path:
    return Path(run_dir) / "tool_recovery" / f"{task_id}.jsonl"


def load_tool_action_log(run_dir: Path, task_id: str) -> list[dict[str, Any]]:
    path = tool_action_log_path(run_dir, task_id)
    if not path.is_file():
        raise FileNotFoundError(path)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid tool recovery log JSON at line {line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"invalid tool recovery log record at line {line_number}")
        records.append(value)
    return records


def verify_tool_recovery_log(
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None,
    task_id: str | None,
) -> tuple[bool, str]:
    if run_dir is None or not task_id:
        return False, "tool recovery action-log context is unavailable"
    try:
        records = load_tool_action_log(run_dir, task_id)
    except (FileNotFoundError, OSError, ValueError) as exc:
        return False, f"tool recovery action log unavailable: {type(exc).__name__}"

    for expected_sequence, record in enumerate(records, 1):
        if record.get("schema") != TOOL_ACTION_LOG_SCHEMA:
            return False, "tool recovery action-log schema mismatch"
        if record.get("sequence") != expected_sequence:
            return False, "tool recovery action-log sequence is not contiguous"
        if record.get("outcome") == "distractor":
            return False, f"inactive or unknown tool selected: {record.get('tool')}"

    incomplete = {str(value) for value in oracle.get("incomplete_case_ids") or []}
    read_transients = {str(value) for value in oracle.get("transient_read_case_ids") or []}
    ambiguous = {str(value) for value in oracle.get("ambiguous_write_case_ids") or []}
    targets = {str(value) for value in oracle.get("target_ids") or []}

    successful_gets = {
        str(record.get("case_id"))
        for record in records
        if record.get("tool") == "cases.get" and record.get("outcome") == "success"
    }
    missing_gets = sorted(incomplete - successful_gets)
    if missing_gets:
        return False, f"incomplete cases were not resolved: {', '.join(missing_gets)}"

    for case_id in sorted(read_transients):
        events = [
            record
            for record in records
            if record.get("tool") == "cases.get" and str(record.get("case_id")) == case_id
        ]
        outcomes = [str(record.get("outcome")) for record in events]
        if not outcomes or outcomes[0] != "transient_failure" or "success" not in outcomes[1:]:
            return False, f"retryable read failure was not recovered: {case_id}"

    process_records = [record for record in records if record.get("tool") == "actions.process"]
    acted_cases = {
        str(record.get("case_id"))
        for record in process_records
        if record.get("outcome") in {
            "applied",
            "duplicate_applied",
            "applied_response_lost",
            "idempotent_replay",
        }
    }
    extra = sorted(acted_cases - targets)
    if extra:
        return False, f"process action used on non-target cases: {', '.join(extra)}"

    for case_id in sorted(targets):
        events = [record for record in process_records if str(record.get("case_id")) == case_id]
        if case_id in ambiguous:
            lost = [record for record in events if record.get("outcome") == "applied_response_lost"]
            replay = [record for record in events if record.get("outcome") == "idempotent_replay"]
            if len(lost) != 1 or not replay:
                return False, f"ambiguous write was not recovered: {case_id}"
            if replay[0].get("idempotency_key") != lost[0].get("idempotency_key"):
                return False, f"ambiguous write used a new idempotency key: {case_id}"
        else:
            applied = [record for record in events if record.get("outcome") == "applied"]
            if len(applied) != 1:
                return False, f"required process action count mismatch: {case_id}"
        if any(record.get("outcome") == "duplicate_applied" for record in events):
            return False, f"non-idempotent duplicate action applied: {case_id}"

    return True, "tool selection, typed calls and recovery provenance verified"


def diagnose_tool_recovery_failure(
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None,
    task_id: str | None,
) -> str | None:
    """Return a deterministic fine-grained failure hint for failed tool tasks."""
    if run_dir is None or not task_id:
        return "RECOVERY_FAILURE"
    try:
        records = load_tool_action_log(run_dir, task_id)
    except (FileNotFoundError, OSError, ValueError):
        return "RECOVERY_FAILURE"

    if any(record.get("outcome") == "distractor" for record in records):
        return "TOOL_SELECTION_ERROR"
    if any(record.get("outcome") == "schema_error" for record in records):
        return "TOOL_SCHEMA_ERROR"

    max_attempts = int(oracle.get("max_attempts_per_operation", 4))
    signatures: dict[tuple[str, str, str], int] = {}
    for record in records:
        signature = (
            str(record.get("tool", "")),
            str(record.get("case_id", "")),
            str(record.get("idempotency_key", "")),
        )
        signatures[signature] = signatures.get(signature, 0) + 1
    if any(count > max_attempts for count in signatures.values()):
        return "RETRY_LOOP"

    read_transients = {str(value) for value in oracle.get("transient_read_case_ids") or []}
    ambiguous = {str(value) for value in oracle.get("ambiguous_write_case_ids") or []}
    for case_id in read_transients:
        events = [
            record
            for record in records
            if record.get("tool") == "cases.get" and str(record.get("case_id")) == case_id
        ]
        if any(record.get("outcome") == "transient_failure" for record in events) and not any(
            record.get("outcome") == "success" for record in events
        ):
            return "RECOVERY_FAILURE"
    for case_id in ambiguous:
        events = [
            record
            for record in records
            if record.get("tool") == "actions.process" and str(record.get("case_id")) == case_id
        ]
        if any(record.get("outcome") == "applied_response_lost" for record in events) and not any(
            record.get("outcome") == "idempotent_replay" for record in events
        ):
            return "RECOVERY_FAILURE"
    return None


__all__ = [
    "TOOL_ACTION_LOG_SCHEMA",
    "TOOL_CONTRACT_SCHEMA",
    "ToolRecoveryError",
    "ToolRecoveryService",
    "diagnose_tool_recovery_failure",
    "load_tool_action_log",
    "tool_action_log_path",
    "verify_tool_recovery_log",
]
