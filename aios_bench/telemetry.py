from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .events import Event, EventCollector


TOOL_PATTERNS = [
    re.compile(r"(?:tool|function)[ _-]*(?:call|use)[: ]+([A-Za-z0-9_.:-]+)", re.I),
    re.compile(r"<tool_call>.*?<name>(.*?)</name>", re.I | re.S),
]
_REFUSAL_STOP_REASONS = {"refusal", "refused", "content_filter", "safety"}


def _compact_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Keep bounded structural telemetry without prompts or bulk tool output."""
    allowed = {
        "type", "event", "id", "toolName", "tool", "name", "toolCallId",
        "call_id", "status", "isError", "willRetry", "usage", "stopReason",
        "responseId", "inferred", "error", "reason",
    }
    compact: dict[str, Any] = {}
    for key in allowed:
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            compact[key] = value[:2000]
        elif isinstance(value, (bool, int, float)):
            compact[key] = value
        elif key == "usage" and isinstance(value, dict):
            compact[key] = {str(k): v for k, v in value.items() if isinstance(v, (int, float))}
    return compact


def _events_from_line(line: str, source: str, collector: EventCollector) -> None:
    text = line.strip()
    if not text:
        return
    lower = text.lower()
    if "error" in lower or "exception" in lower or "traceback" in lower:
        collector.add("error", source=source, message=text[:1000], inferred=True)
    if "retry" in lower or "retrying" in lower:
        collector.add("retry", source=source, message=text[:1000], inferred=True)
    if any(x in lower for x in ("memory read", "recall memory", "search memory")):
        collector.add("memory_read", source=source, message=text[:1000], inferred=True)
    if any(x in lower for x in ("memory write", "save memory", "remember")):
        collector.add("memory_write", source=source, message=text[:1000], inferred=True)
    if "subagent" in lower and any(x in lower for x in ("start", "spawn", "delegate")):
        collector.add("subagent_start", source=source, message=text[:1000], inferred=True)
    if "subagent" in lower and any(x in lower for x in ("end", "finish", "complete")):
        collector.add("subagent_end", source=source, message=text[:1000], inferred=True)
    if any(x in lower for x in ("file read", "read file", "cat ", "read_file")):
        collector.add("file_read", source=source, message=text[:1000], inferred=True)
    if any(x in lower for x in ("file write", "write file", "write_file")):
        collector.add("file_write", source=source, message=text[:1000], inferred=True)
    for pattern in TOOL_PATTERNS:
        match = pattern.search(text)
        if match:
            collector.add("tool_call", source=source, name=match.group(1)[:200], raw=text[:1000], inferred=True)
            break


def _usage(item: dict[str, Any]) -> dict[str, int]:
    usage = item.get("usage") or item.get("message", {}).get("usage") or {}
    return {
        "input": int(usage.get("input", 0) or 0),
        "output": int(usage.get("output", 0) or 0),
        "reasoning": int(usage.get("reasoning", 0) or 0),
        "total": int(usage.get("totalTokens", usage.get("total_tokens", 0)) or 0),
    }


def _record_assistant_message(
    collector: EventCollector,
    *,
    source: str,
    message: dict[str, Any],
    turn: bool = False,
) -> None:
    usage = _usage(message)
    stop_reason = message.get("stopReason")
    collector.add(
        "assistant_message",
        source=source,
        content=message.get("content", []),
        usage=usage,
        stop_reason=stop_reason,
        response_id=message.get("responseId"),
        turn=turn,
    )
    if str(stop_reason or "").strip().lower() in _REFUSAL_STOP_REASONS:
        collector.add("refusal", source=source, stop_reason=stop_reason)


def parse_pi_rpc(text: str, *, source: str = "piagent") -> list[Event]:
    """Normalize Pi RPC JSONL events into AIOS-bench canonical events."""
    collector = EventCollector()
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            _events_from_line(line, source, collector)
            continue

        kind = item.get("type")
        if kind == "response":
            continue
        if kind == "agent_start":
            collector.add("session_start", source=source, payload=_compact_payload(item))
        elif kind == "agent_settled":
            collector.add("session_end", source=source, payload=_compact_payload(item))
        elif kind == "message_end":
            message = item.get("message") or {}
            if message.get("role") == "assistant":
                _record_assistant_message(collector, source=source, message=message)
        elif kind == "turn_end":
            message = item.get("message") or {}
            _record_assistant_message(collector, source=source, message=message, turn=True)
            for result in item.get("toolResults", []) or []:
                collector.add(
                    "tool_result",
                    source=source,
                    payload=_compact_payload(result) if isinstance(result, dict) else {},
                )
        elif kind == "tool_execution_start":
            collector.add(
                "tool_call", source=source, tool=item.get("toolName", item.get("name")),
                call_id=item.get("toolCallId", item.get("id")),
            )
        elif kind == "tool_execution_end":
            collector.add(
                "tool_result", source=source, tool=item.get("toolName", item.get("name")),
                call_id=item.get("toolCallId", item.get("id")), is_error=bool(item.get("isError")),
            )
        elif kind == "tool_execution_update":
            collector.add("tool_result", source=source, update=True, call_id=item.get("toolCallId", item.get("id")))
        elif kind == "bash_execution_update":
            collector.add("terminal", source=source, call_id=item.get("toolCallId", item.get("id")))
        elif kind in {"auto_retry_start", "summarization_retry_attempt_start"}:
            collector.add("retry", source=source, payload=_compact_payload(item))
        elif kind == "extension_error":
            collector.add("error", source=source, payload=_compact_payload(item))
        elif kind == "agent_end":
            if item.get("willRetry"):
                collector.add("retry", source=source, payload=_compact_payload(item))
        elif kind in {"refusal", "refused", "safety_refusal"}:
            collector.add("refusal", source=source, payload=_compact_payload(item))
        elif kind == "message_update":
            continue
        elif kind in {"queue_update", "compaction_start", "compaction_end", "turn_start", "message_start"}:
            collector.add("unknown", source=source, rpc_type=kind)
        else:
            collector.add("unknown", source=source, rpc_type=kind)
    return collector.events


def _opencode_part(item: dict[str, Any]) -> dict[str, Any]:
    part = item.get("part")
    return part if isinstance(part, dict) else {}


def _opencode_error_message(item: dict[str, Any]) -> str | None:
    error = item.get("error")
    if isinstance(error, str):
        return error[:2000]
    if not isinstance(error, dict):
        return None
    data = error.get("data")
    if isinstance(data, dict) and isinstance(data.get("message"), str):
        return data["message"][:2000]
    if isinstance(error.get("message"), str):
        return error["message"][:2000]
    if isinstance(error.get("name"), str):
        return error["name"][:2000]
    return None


def parse_opencode_jsonl(text: str, *, source: str = "opencode") -> list[Event]:
    """Normalize ``opencode run --format json`` events.

    OpenCode reports one ``tool_use`` part for a tool call/state and one
    ``step_finish`` part per model step.  Tool input/output is deliberately not
    copied into benchmark telemetry.  Step token counts are accumulated so the
    existing trajectory model observes whole-session usage rather than only the
    largest individual model step.

    A structured ``task`` tool invocation is native delegation evidence.  It is
    therefore normalized to a non-inferred ``subagent_start`` event; terminal
    task states also produce ``subagent_end``.  Plain-text mentions of delegation
    continue to be ignored by deterministic subagent grading.
    """
    collector = EventCollector()
    seen_calls: set[str] = set()
    seen_results: set[str] = set()
    seen_subagents: set[str] = set()
    seen_subagent_ends: set[str] = set()
    cumulative = {"input": 0, "output": 0, "reasoning": 0, "total": 0}
    structured = False
    session_id: str | None = None

    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            _events_from_line(line, source, collector)
            continue
        if not isinstance(item, dict):
            continue

        kind = str(item.get("type", "")).strip().lower().replace("-", "_")
        part = _opencode_part(item)
        if not kind:
            continue
        if not structured:
            session_id = str(item.get("sessionID") or part.get("sessionID") or "") or None
            collector.add("session_start", source=source, session_id=session_id, inferred=False)
            structured = True

        if kind == "tool_use":
            tool = str(part.get("tool") or item.get("tool") or "").strip()
            call_id = str(part.get("callID") or item.get("callID") or part.get("id") or "").strip()
            state = part.get("state") if isinstance(part.get("state"), dict) else {}
            status = str(state.get("status") or "").strip().lower()
            call_key = call_id or f"{tool}:{part.get('id', '')}"

            if call_key not in seen_calls:
                collector.add(
                    "tool_call",
                    source=source,
                    tool=tool or None,
                    call_id=call_id or None,
                    status=status or None,
                    inferred=False,
                )
                seen_calls.add(call_key)
                if tool == "read":
                    collector.add("file_read", source=source, tool=tool, call_id=call_id or None, inferred=False)
                elif tool in {"write", "edit", "patch", "apply_patch"}:
                    collector.add("file_write", source=source, tool=tool, call_id=call_id or None, inferred=False)
                elif tool in {"bash", "shell"}:
                    collector.add("terminal", source=source, tool=tool, call_id=call_id or None, inferred=False)

            if tool == "task" and call_key not in seen_subagents:
                collector.add(
                    "subagent_start",
                    source=source,
                    tool="task",
                    call_id=call_id or None,
                    status=status or None,
                    inferred=False,
                )
                seen_subagents.add(call_key)

            terminal = status in {"completed", "complete", "error", "failed", "cancelled", "canceled"}
            if terminal and call_key not in seen_results:
                collector.add(
                    "tool_result",
                    source=source,
                    tool=tool or None,
                    call_id=call_id or None,
                    status=status,
                    is_error=status in {"error", "failed"},
                    inferred=False,
                )
                seen_results.add(call_key)
            if terminal and tool == "task" and call_key not in seen_subagent_ends:
                collector.add(
                    "subagent_end",
                    source=source,
                    tool="task",
                    call_id=call_id or None,
                    status=status,
                    inferred=False,
                )
                seen_subagent_ends.add(call_key)

        elif kind == "step_finish":
            tokens = part.get("tokens") if isinstance(part.get("tokens"), dict) else {}
            step_input = int(tokens.get("input", 0) or 0)
            step_output = int(tokens.get("output", 0) or 0)
            step_reasoning = int(tokens.get("reasoning", 0) or 0)
            cumulative["input"] += step_input
            cumulative["output"] += step_output
            cumulative["reasoning"] += step_reasoning
            cumulative["total"] += step_input + step_output + step_reasoning
            reason = str(part.get("reason") or item.get("reason") or "").strip()
            collector.add(
                "assistant_message",
                source=source,
                usage=dict(cumulative),
                stop_reason=reason or None,
                step=True,
                inferred=False,
            )
            normalized_reason = reason.lower().replace("-", "_")
            if normalized_reason in _REFUSAL_STOP_REASONS:
                collector.add("refusal", source=source, stop_reason=reason, inferred=False)

        elif kind == "text":
            collector.add("assistant_message", source=source, part_id=part.get("id"), inferred=False)
        elif kind == "error":
            collector.add(
                "error",
                source=source,
                message=_opencode_error_message(item),
                inferred=False,
            )
        elif kind in {"retry", "auto_retry", "retry_start"}:
            collector.add("retry", source=source, inferred=False)
        elif kind in {"refusal", "refused", "safety_refusal"}:
            collector.add("refusal", source=source, inferred=False)
        elif kind in {"step_start", "message_start", "message_end"}:
            continue
        else:
            collector.add("unknown", source=source, opencode_type=kind)

    if structured:
        collector.add(
            "session_end",
            source=source,
            session_id=session_id,
            usage=dict(cumulative),
            inferred=False,
        )
    return collector.events


def parse_text(text: str, *, source: str) -> list[Event]:
    collector = EventCollector()
    for line in text.splitlines():
        _events_from_line(line, source, collector)
    return collector.events


def parse_jsonl(text: str, *, source: str) -> list[Event]:
    collector = EventCollector()
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            _events_from_line(line, source, collector)
            continue
        kind = str(item.get("type", item.get("event", "unknown"))).lower()
        mapping = {
            "tool_call": "tool_call",
            "tool_use": "tool_call",
            "tool_result": "tool_result",
            "message": "assistant_message",
            "assistant": "assistant_message",
            "error": "error",
            "retry": "retry",
            "memory_read": "memory_read",
            "memory_write": "memory_write",
            "subagent_start": "subagent_start",
            "subagent_end": "subagent_end",
            "file_read": "file_read",
            "file_write": "file_write",
            "refusal": "refusal",
            "refused": "refusal",
            "safety_refusal": "refusal",
        }
        event_type = mapping.get(kind, "unknown")
        collector.add(event_type, source=source, payload=_compact_payload(item))
    return collector.events


def parse_output(stdout: str, stderr: str = "", *, source: str) -> list[Event]:
    if source == "piagent":
        events = parse_pi_rpc(stdout, source=source)
    elif source == "opencode":
        events = parse_opencode_jsonl(stdout, source=source)
    else:
        events = parse_jsonl(stdout, source=source)
    events.extend(parse_text(stderr, source=f"{source}:stderr"))
    if not events and stdout:
        events = parse_text(stdout, source=source)
    return events


def count_files(workspace: Path) -> tuple[int, int]:
    """Return file count and total bytes; used as a coarse fallback signal."""
    files = list(workspace.rglob("*"))
    return sum(p.is_file() for p in files), sum(p.stat().st_size for p in files if p.is_file())
