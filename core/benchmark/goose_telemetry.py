from __future__ import annotations

import json
from typing import Any

from .events import Event, EventCollector


_TERMINAL_TOOLS = {"shell", "developer__shell"}
_FILE_READ_TOOLS = {"read", "developer__read", "text_editor", "developer__text_editor"}
_FILE_WRITE_TOOLS = {
    "write", "edit", "developer__write", "developer__edit",
    "text_editor", "developer__text_editor",
}
_DELEGATE_TOOLS = {"delegate", "summon__delegate"}


def _tool_request(content: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Return (call_id, tool_name, status) without retaining arguments."""
    call_id = content.get("id")
    tool_call = content.get("toolCall")
    if not isinstance(tool_call, dict):
        return str(call_id) if call_id is not None else None, None, None
    status = tool_call.get("status")
    value = tool_call.get("value")
    tool = value.get("name") if isinstance(value, dict) else None
    return (
        str(call_id) if call_id is not None else None,
        str(tool) if tool is not None else None,
        str(status) if status is not None else None,
    )


def _tool_response(content: dict[str, Any]) -> tuple[str | None, str | None, bool]:
    """Return (call_id, status, is_error) without retaining result content."""
    call_id = content.get("id")
    result = content.get("toolResult")
    if not isinstance(result, dict):
        return str(call_id) if call_id is not None else None, None, False
    status = result.get("status")
    normalized = str(status or "").strip().lower()
    return (
        str(call_id) if call_id is not None else None,
        str(status) if status is not None else None,
        normalized in {"error", "failed", "failure"},
    )


def parse_goose_stream_json(text: str, *, source: str = "goose") -> list[Event]:
    """Normalize ``goose run --output-format stream-json`` NDJSON.

    Goose's stream envelope uses top-level ``message``, ``notification``,
    ``error`` and ``complete`` events.  Nested message content uses the
    camelCase ``toolRequest``/``toolResponse`` discriminators.  Tool arguments,
    message text, and tool-result payloads are intentionally excluded from the
    canonical benchmark events.

    The default-enabled Summon extension exposes an unprefixed ``delegate``
    tool that creates a real subagent session.  A structured delegate request is
    therefore non-inferred delegation evidence; the matching tool response ends
    that subagent observation.  Plain-text claims never count.
    """
    collector = EventCollector()
    structured = False
    delegate_calls: set[str] = set()
    ended_delegate_calls: set[str] = set()
    saw_complete = False

    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue

        kind = str(item.get("type", "")).strip().lower().replace("-", "_")
        if kind not in {"message", "notification", "error", "complete"}:
            collector.add("unknown", source=source, goose_type=kind or "unknown")
            continue

        if not structured:
            collector.add("session_start", source=source, inferred=False)
            structured = True

        if kind == "message":
            message = item.get("message")
            if not isinstance(message, dict):
                message = item
            role = str(message.get("role", "")).lower()
            content_list = message.get("content")
            if not isinstance(content_list, list):
                continue

            saw_assistant_content = False
            for content in content_list:
                if not isinstance(content, dict):
                    continue
                content_type = str(content.get("type", ""))
                if content_type == "toolRequest":
                    call_id, tool, status = _tool_request(content)
                    collector.add(
                        "tool_call",
                        source=source,
                        tool=tool,
                        call_id=call_id,
                        status=status,
                        inferred=False,
                    )
                    if tool in _TERMINAL_TOOLS:
                        collector.add("terminal", source=source, tool=tool, call_id=call_id, inferred=False)
                    if tool in _FILE_READ_TOOLS:
                        collector.add("file_read", source=source, tool=tool, call_id=call_id, inferred=False)
                    if tool in _FILE_WRITE_TOOLS:
                        collector.add("file_write", source=source, tool=tool, call_id=call_id, inferred=False)
                    if tool in _DELEGATE_TOOLS:
                        key = call_id or f"delegate:{len(delegate_calls)}"
                        delegate_calls.add(key)
                        collector.add(
                            "subagent_start",
                            source=source,
                            tool=tool,
                            call_id=call_id,
                            inferred=False,
                        )
                    saw_assistant_content = saw_assistant_content or role == "assistant"
                elif content_type == "toolResponse":
                    call_id, status, is_error = _tool_response(content)
                    collector.add(
                        "tool_result",
                        source=source,
                        call_id=call_id,
                        status=status,
                        is_error=is_error,
                        inferred=False,
                    )
                    if call_id and call_id in delegate_calls and call_id not in ended_delegate_calls:
                        collector.add(
                            "subagent_end",
                            source=source,
                            call_id=call_id,
                            status=status,
                            is_error=is_error,
                            inferred=False,
                        )
                        ended_delegate_calls.add(call_id)
                elif content_type in {"error", "Error"}:
                    collector.add("error", source=source, inferred=False)
                elif role == "assistant" and content_type in {
                    "text", "thinking", "redactedThinking", "reasoning",
                }:
                    saw_assistant_content = True

            if role == "assistant" and saw_assistant_content:
                collector.add("assistant_message", source=source, inferred=False)

        elif kind == "error":
            # Keep only bounded structural status; error body may contain prompt
            # or provider output and is intentionally not persisted here.
            collector.add("error", source=source, inferred=False)
        elif kind == "notification":
            collector.add("unknown", source=source, goose_type="notification", inferred=False)
        elif kind == "complete":
            total = int(item.get("total_tokens", 0) or 0)
            collector.add(
                "session_end",
                source=source,
                usage={"input": 0, "output": 0, "reasoning": 0, "total": total},
                inferred=False,
            )
            saw_complete = True

    if structured and not saw_complete:
        collector.add("session_end", source=source, inferred=False)
    return collector.events
