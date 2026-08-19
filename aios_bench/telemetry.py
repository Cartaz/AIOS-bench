from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

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


def parse_text(text: str, *, source: str) -> list[Event]:
    collector = EventCollector()
    for line in text.splitlines():
        _events_from_line(line, source, collector)
    return collector.events


def parse_jsonl(text: str, *, source: str) -> list[Event]:
    import json

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
    events = parse_jsonl(stdout, source=source)
    events.extend(parse_text(stderr, source=f"{source}:stderr"))
    if not events and stdout:
        events = parse_text(stdout, source=source)
    return events


def count_files(workspace: Path) -> tuple[int, int]:
    """Return file count and total bytes; used as a coarse fallback signal."""
    files = list(workspace.rglob("*"))
    return sum(p.is_file() for p in files), sum(p.stat().st_size for p in files if p.is_file())
