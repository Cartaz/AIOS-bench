from __future__ import annotations

import json
from typing import Any, Mapping

from .events import Event, EventCollector


_SUBAGENT_TOOLS = {"Agent", "Task"}
_TERMINAL_TOOLS = {
    "Bash", "Shell", "shell", "shell_command", "ShellCommand",
    "exec_command", "RunShellCommand", "run_shell_command",
}
_FILE_READ_TOOLS = {
    "Read", "read_file", "ReadFile", "read_file_gemini", "ReadFileGemini",
    "read_many_files", "ReadManyFiles", "list_dir", "ListDir", "Glob", "Grep",
}
_FILE_WRITE_TOOLS = {
    "Edit", "Write", "MultiEdit", "apply_patch", "ApplyPatch", "replace",
    "write_file", "write_file_gemini", "WriteFileGemini",
}
_REFUSAL_STOP_REASONS = {"refusal", "refused", "content_filter", "safety"}


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _first_int(value: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        if key in value:
            return _integer(value.get(key))
    return 0


def _usage(value: Any) -> dict[str, int]:
    """Normalize known Letta usage spellings without inventing missing fields."""
    if not isinstance(value, Mapping):
        return {"input": 0, "output": 0, "reasoning": 0, "total": 0}
    input_tokens = _first_int(value, "input_tokens", "prompt_tokens", "input")
    output_tokens = _first_int(value, "output_tokens", "completion_tokens", "output")
    reasoning_tokens = _first_int(value, "reasoning_tokens", "reasoning")
    total_tokens = _first_int(value, "total_tokens", "total")
    if total_tokens <= 0 and (input_tokens or output_tokens or reasoning_tokens):
        total_tokens = input_tokens + output_tokens + reasoning_tokens
    return {
        "input": input_tokens,
        "output": output_tokens,
        "reasoning": reasoning_tokens,
        "total": total_tokens,
    }


def _tool_call(item: Mapping[str, Any]) -> tuple[str | None, str | None]:
    tool_call = item.get("tool_call")
    if not isinstance(tool_call, Mapping):
        return None, None
    name = tool_call.get("name")
    call_id = tool_call.get("tool_call_id")
    return (
        str(name) if name is not None else None,
        str(call_id) if call_id is not None else None,
    )


def parse_letta_stream_json(text: str, *, source: str = "letta") -> list[Event]:
    """Normalize Letta Code headless ``stream-json`` output.

    The wire protocol emits explicit system/init, message, tool lifecycle,
    retry/error and final result envelopes.  Canonical telemetry retains only
    bounded structure: message text, reasoning, tool arguments, stdout/stderr
    and tool returns are never copied into benchmark events.

    Letta's internal ``Task`` subagent tool is currently surfaced to models as
    ``Agent``; both names are accepted so the benchmark remains compatible with
    older/newer Letta Code releases.  Only a structured tool_call_message is
    delegation evidence.
    """
    collector = EventCollector()
    call_tools: dict[str, str] = {}
    subagent_calls: set[str] = set()
    ended_subagents: set[str] = set()
    saw_session_start = False
    saw_session_end = False

    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            # stream-json owns stdout; malformed/non-JSON lines are not trusted
            # as structured telemetry and cannot establish delegation.
            continue
        if not isinstance(item, dict):
            continue

        kind = str(item.get("type", "")).strip().lower()
        session_id = item.get("session_id")

        if kind == "system" and str(item.get("subtype", "")).lower() == "init":
            collector.add(
                "session_start",
                source=source,
                session_id=str(session_id) if session_id is not None else None,
                conversation_id=(
                    str(item.get("conversation_id"))
                    if item.get("conversation_id") is not None else None
                ),
                model=str(item.get("model")) if item.get("model") is not None else None,
                permission_mode=(
                    str(item.get("permission_mode"))
                    if item.get("permission_mode") is not None else None
                ),
                tool_count=len(item.get("tools") or []) if isinstance(item.get("tools"), list) else 0,
                inferred=False,
            )
            saw_session_start = True
            continue

        if not saw_session_start:
            collector.add(
                "session_start",
                source=source,
                session_id=str(session_id) if session_id is not None else None,
                inferred=False,
            )
            saw_session_start = True

        if kind == "message":
            message_type = str(item.get("message_type", "")).strip().lower()
            if message_type == "tool_call_message":
                tool, call_id = _tool_call(item)
                collector.add(
                    "tool_call",
                    source=source,
                    tool=tool,
                    call_id=call_id,
                    inferred=False,
                )
                if call_id and tool:
                    call_tools[call_id] = tool
                if tool in _TERMINAL_TOOLS:
                    collector.add("terminal", source=source, tool=tool, call_id=call_id, inferred=False)
                if tool in _FILE_READ_TOOLS:
                    collector.add("file_read", source=source, tool=tool, call_id=call_id, inferred=False)
                if tool in _FILE_WRITE_TOOLS:
                    collector.add("file_write", source=source, tool=tool, call_id=call_id, inferred=False)
                if tool in _SUBAGENT_TOOLS:
                    key = call_id or f"subagent:{len(subagent_calls)}"
                    if key not in subagent_calls:
                        collector.add(
                            "subagent_start",
                            source=source,
                            tool=tool,
                            call_id=call_id,
                            inferred=False,
                        )
                        subagent_calls.add(key)
            elif message_type == "tool_return_message":
                call_id_value = item.get("tool_call_id")
                call_id = str(call_id_value) if call_id_value is not None else None
                status_value = item.get("status")
                status = str(status_value) if status_value is not None else None
                is_error = str(status or "").lower() in {"error", "failed", "failure"}
                tool = call_tools.get(call_id or "")
                collector.add(
                    "tool_result",
                    source=source,
                    tool=tool,
                    call_id=call_id,
                    status=status,
                    is_error=is_error,
                    inferred=False,
                )
                key = call_id or ""
                if tool in _SUBAGENT_TOOLS and key in subagent_calls and key not in ended_subagents:
                    collector.add(
                        "subagent_end",
                        source=source,
                        tool=tool,
                        call_id=call_id,
                        status=status,
                        is_error=is_error,
                        inferred=False,
                    )
                    ended_subagents.add(key)
            elif message_type == "assistant_message":
                collector.add("assistant_message", source=source, inferred=False)
            # reasoning and other content messages are intentionally omitted.

        elif kind == "error":
            stop_reason = item.get("stop_reason")
            collector.add(
                "error",
                source=source,
                stop_reason=str(stop_reason) if stop_reason is not None else None,
                inferred=False,
            )
            if str(stop_reason or "").strip().lower() in _REFUSAL_STOP_REASONS:
                collector.add("refusal", source=source, stop_reason=stop_reason, inferred=False)
        elif kind == "retry":
            collector.add(
                "retry",
                source=source,
                reason=str(item.get("reason")) if item.get("reason") is not None else None,
                attempt=_integer(item.get("attempt")),
                inferred=False,
            )
        elif kind == "recovery":
            collector.add(
                "retry",
                source=source,
                recovery_type=(
                    str(item.get("recovery_type"))
                    if item.get("recovery_type") is not None else None
                ),
                inferred=False,
            )
        elif kind == "result":
            subtype = str(item.get("subtype", "")).strip().lower()
            stop_reason = item.get("stop_reason")
            usage = _usage(item.get("usage"))
            if subtype == "error":
                collector.add(
                    "error",
                    source=source,
                    stop_reason=str(stop_reason) if stop_reason is not None else None,
                    inferred=False,
                )
            if str(stop_reason or "").strip().lower() in _REFUSAL_STOP_REASONS:
                collector.add("refusal", source=source, stop_reason=stop_reason, inferred=False)
            collector.add(
                "session_end",
                source=source,
                session_id=str(session_id) if session_id is not None else None,
                conversation_id=(
                    str(item.get("conversation_id"))
                    if item.get("conversation_id") is not None else None
                ),
                subtype=subtype or None,
                stop_reason=str(stop_reason) if stop_reason is not None else None,
                usage=usage,
                inferred=False,
            )
            saw_session_end = True
        elif kind in {
            "approval_requested", "approval_received", "tool_execution_started",
            "tool_execution_finished", "auto_approval", "stream_event", "cancel_ack",
        }:
            # These are useful lifecycle envelopes but would duplicate canonical
            # call/result records or expose tool payloads.  Do not persist them.
            continue
        else:
            collector.add("unknown", source=source, letta_type=kind or "unknown")

    if saw_session_start and not saw_session_end:
        collector.add("session_end", source=source, inferred=False)
    return collector.events
