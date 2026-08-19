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


def _events_from_line(line: str, source: str, collector: EventCollector) -> None:
    text = line.strip()
    if not text:
        return
    lower = text.lower()
    if "error" in lower or "exception" in lower or "traceback" in lower:
        collector.add("error", source=source, message=text[:1000])
    if "retry" in lower or "retrying" in lower:
        collector.add("retry", source=source, message=text[:1000])
    if any(x in lower for x in ("memory read", "recall memory", "search memory")):
        collector.add("memory_read", source=source, message=text[:1000])
    if any(x in lower for x in ("memory write", "save memory", "remember")):
        collector.add("memory_write", source=source, message=text[:1000])
    if "subagent" in lower and any(x in lower for x in ("start", "spawn", "delegate")):
        collector.add("subagent_start", source=source, message=text[:1000])
    if "subagent" in lower and any(x in lower for x in ("end", "finish", "complete")):
        collector.add("subagent_end", source=source, message=text[:1000])
    if any(x in lower for x in ("file read", "read file", "cat ", "read_file")):
        collector.add("file_read", source=source, message=text[:1000])
    if any(x in lower for x in ("file write", "write file", "write_file")):
        collector.add("file_write", source=source, message=text[:1000])
    for pattern in TOOL_PATTERNS:
        match = pattern.search(text)
        if match:
            collector.add("tool_call", source=source, name=match.group(1)[:200], raw=text[:1000])
            break


def _usage(item: dict[str, Any]) -> dict[str, int]:
    usage = item.get("usage") or item.get("message", {}).get("usage") or {}
    return {
        "input": int(usage.get("input", 0) or 0),
        "output": int(usage.get("output", 0) or 0),
        "reasoning": int(usage.get("reasoning", 0) or 0),
        "total": int(usage.get("totalTokens", usage.get("total_tokens", 0)) or 0),
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
            collector.add("session_start", source=source, payload=item)
        elif kind == "agent_settled":
            collector.add("session_end", source=source, payload=item)
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
                collector.add("tool_result", source=source, payload=result)
        elif kind == "tool_execution_start":
            collector.add("tool_call", source=source, tool=item.get("toolName", item.get("name")),
                           call_id=item.get("toolCallId", item.get("id")), payload=item)
        elif kind == "tool_execution_end":
            collector.add("tool_result", source=source, tool=item.get("toolName", item.get("name")),
                           call_id=item.get("toolCallId", item.get("id")), payload=item)
        elif kind == "tool_execution_update":
            collector.add("tool_result", source=source, update=True, payload=item)
        elif kind == "bash_execution_update":
            collector.add("terminal", source=source, payload=item)
        elif kind in {"auto_retry_start", "summarization_retry_attempt_start"}:
            collector.add("retry", source=source, payload=item)
        elif kind == "extension_error":
            collector.add("error", source=source, payload=item)
        elif kind == "agent_end":
            if item.get("willRetry"):
                collector.add("retry", source=source, payload=item)
        elif kind == "message_update":
            update = item.get("assistantMessageEvent") or {}
            if update.get("type") == "text_delta":
                collector.add("assistant_message", source=source, delta=update.get("delta", ""), streaming=True)
        elif kind in {"queue_update", "compaction_start", "compaction_end", "turn_start", "message_start"}:
            # Preserve protocol lifecycle information without forcing it into a
            # benchmark capability category.
            collector.add("unknown", source=source, rpc_type=kind, payload=item)
        else:
            collector.add("unknown", source=source, rpc_type=kind, payload=item)
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
        collector.add(event_type, source=source, payload=item)
    return collector.events


def parse_output(stdout: str, stderr: str = "", *, source: str) -> list[Event]:
    if source == "piagent":
        events = parse_pi_rpc(stdout, source=source)
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
