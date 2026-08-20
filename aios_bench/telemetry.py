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


def _compact_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Keep bounded structural telemetry without prompts or bulk tool output."""
    allowed = {
        "type", "event", "id", "toolName", "tool", "name", "toolCallId",
        "call_id", "status", "isError", "willRetry", "usage", "stopReason",
        "responseId", "inferred", "error", "reason", "sessionID",
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


def _opencode_usage(part: dict[str, Any]) -> dict[str, int]:
    tokens = part.get("tokens") or {}
    input_tokens = int(tokens.get("input", 0) or 0)
    output_tokens = int(tokens.get("output", 0) or 0)
    reasoning_tokens = int(tokens.get("reasoning", 0) or 0)
    total = int(tokens.get("total", 0) or 0)
    if not total:
        total = input_tokens + output_tokens + reasoning_tokens
    return {
        "input": input_tokens,
        "output": output_tokens,
        "reasoning": reasoning_tokens,
        "total": total,
    }


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
            # RPC command acknowledgements are protocol metadata, not agent events.
            continue
        if kind == "agent_start":
            collector.add("session_start", source=source, payload=_compact_payload(item))
        elif kind == "agent_settled":
            collector.add("session_end", source=source, payload=_compact_payload(item))
        elif kind == "message_end":
            message = item.get("message") or {}
            role = message.get("role")
            usage = _usage(message)
            if role == "assistant":
                collector.add("assistant_message", source=source, content=message.get("content", []), usage=usage,
                               stop_reason=message.get("stopReason"), response_id=message.get("responseId"))
        elif kind == "turn_end":
            message = item.get("message") or {}
            usage = _usage(message)
            collector.add("assistant_message", source=source, content=message.get("content", []), usage=usage,
                           stop_reason=message.get("stopReason"), response_id=message.get("responseId"), turn=True)
            for result in item.get("toolResults", []) or []:
                collector.add("tool_result", source=source,
                              payload=_compact_payload(result) if isinstance(result, dict) else {})
        elif kind == "tool_execution_start":
            collector.add("tool_call", source=source, tool=item.get("toolName", item.get("name")),
                           call_id=item.get("toolCallId", item.get("id")))
        elif kind == "tool_execution_end":
            collector.add("tool_result", source=source, tool=item.get("toolName", item.get("name")),
                           call_id=item.get("toolCallId", item.get("id")), is_error=bool(item.get("isError")))
        elif kind == "tool_execution_update":
            collector.add("tool_result", source=source, update=True,
                          call_id=item.get("toolCallId", item.get("id")))
        elif kind == "bash_execution_update":
            collector.add("terminal", source=source, call_id=item.get("toolCallId", item.get("id")))
        elif kind in {"auto_retry_start", "summarization_retry_attempt_start"}:
            collector.add("retry", source=source, payload=_compact_payload(item))
        elif kind == "extension_error":
            collector.add("error", source=source, payload=_compact_payload(item))
        elif kind == "agent_end":
            if item.get("willRetry"):
                collector.add("retry", source=source, payload=_compact_payload(item))
        elif kind == "message_update":
            # message_end carries the final content and usage. Persisting every
            # streaming delta made canonical trajectories quadratic in size.
            continue
        elif kind in {"queue_update", "compaction_start", "compaction_end", "turn_start", "message_start"}:
            # Preserve protocol lifecycle information without forcing it into a
            # benchmark capability category.
            collector.add("unknown", source=source, rpc_type=kind)
        else:
            collector.add("unknown", source=source, rpc_type=kind)
    return collector.events


def parse_opencode_jsonl(text: str, *, source: str = "opencode") -> list[Event]:
    """Normalize ``opencode run --format json`` NDJSON into canonical events.

    OpenCode emits completed tool parts rather than a separate start/end pair,
    so one ``tool_use`` record becomes both a canonical call and result.  The
    ``task`` tool is deliberately *not* converted into structured subagent
    telemetry: current OpenCode headless streams do not expose child-session
    events, so doing so would overstate harness observability.
    """

    collector = EventCollector()
    session_started = False
    session_ended = False

    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            _events_from_line(line, source, collector)
            continue
        if not isinstance(item, dict):
            collector.add("unknown", source=source)
            continue

        kind = str(item.get("type", "unknown"))
        part = item.get("part") if isinstance(item.get("part"), dict) else {}
        session_id = item.get("sessionID") or part.get("sessionID")

        if kind == "step_start":
            if not session_started:
                collector.add("session_start", source=source, session_id=session_id)
                session_started = True
            else:
                collector.add("unknown", source=source, opencode_type=kind, session_id=session_id)
            continue

        if kind == "text":
            collector.add(
                "assistant_message",
                source=source,
                content=str(part.get("text", ""))[:20000],
                session_id=session_id,
            )
            continue

        if kind == "tool_use":
            tool = str(part.get("tool", "unknown"))[:200]
            call_id = part.get("callID") or part.get("id")
            state = part.get("state") if isinstance(part.get("state"), dict) else {}
            status = str(state.get("status", "unknown"))
            is_error = status == "error"
            collector.add(
                "tool_call", source=source, tool=tool, call_id=call_id,
                status=status, session_id=session_id,
            )
            collector.add(
                "tool_result", source=source, tool=tool, call_id=call_id,
                is_error=is_error, status=status, session_id=session_id,
            )
            normalized = tool.lower().replace("-", "_")
            if normalized in {"bash", "shell", "terminal"}:
                collector.add("terminal", source=source, tool=tool, call_id=call_id)
            if normalized in {"read", "read_file"}:
                collector.add("file_read", source=source, tool=tool, call_id=call_id)
            if normalized in {"write", "write_file", "edit", "apply_patch", "patch"}:
                collector.add("file_write", source=source, tool=tool, call_id=call_id)
            continue

        if kind == "step_finish":
            usage = _opencode_usage(part)
            reason = part.get("reason")
            if reason == "stop" and not session_ended:
                collector.add(
                    "session_end", source=source, session_id=session_id,
                    usage=usage, stop_reason=reason,
                )
                session_ended = True
            else:
                collector.add(
                    "unknown", source=source, opencode_type=kind,
                    session_id=session_id, usage=usage, stop_reason=reason,
                )
            continue

        if kind == "error":
            collector.add(
                "error", source=source, session_id=session_id,
                error=str(item.get("error", "OpenCode error"))[:2000],
            )
            continue

        if kind == "reasoning":
            collector.add("unknown", source=source, opencode_type=kind, session_id=session_id)
            continue

        collector.add("unknown", source=source, opencode_type=kind, session_id=session_id)

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
