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


def _claude_usage(item: dict[str, Any]) -> dict[str, int]:
    usage = item.get("usage")
    if not isinstance(usage, dict):
        message = item.get("message")
        usage = message.get("usage") if isinstance(message, dict) else {}
    if not isinstance(usage, dict):
        usage = {}
    direct_input = int(usage.get("input_tokens", usage.get("input", 0)) or 0)
    cache_creation = int(usage.get("cache_creation_input_tokens", 0) or 0)
    cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
    output = int(usage.get("output_tokens", usage.get("output", 0)) or 0)
    reasoning = int(usage.get("reasoning_tokens", usage.get("reasoning", 0)) or 0)
    input_tokens = direct_input + cache_creation + cache_read
    return {
        "input": input_tokens,
        "output": output,
        "reasoning": reasoning,
        "total": input_tokens + output + reasoning,
    }


def _claude_content_blocks(item: dict[str, Any]) -> list[dict[str, Any]]:
    message = item.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def parse_claude_jsonl(text: str, *, source: str = "claude") -> list[Event]:
    """Normalize Claude Code ``-p --output-format stream-json`` events.

    Claude Code wraps Anthropic message content inside top-level ``assistant``
    and ``user`` records. Tool calls and results therefore need explicit nested
    parsing rather than the generic JSONL mapper. Native ``Agent`` tool calls are
    authoritative delegation evidence and become non-inferred subagent events.
    Prompts, tool input, tool output and final response text are intentionally
    omitted from benchmark telemetry.
    """
    collector = EventCollector()
    tool_names: dict[str, str] = {}
    seen_calls: set[str] = set()
    seen_results: set[str] = set()
    seen_subagents: set[str] = set()
    seen_subagent_ends: set[str] = set()
    session_id: str | None = None
    started = False
    ended = False

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
        subtype = str(item.get("subtype", "")).strip().lower().replace("-", "_")

        if kind == "system":
            if subtype == "init":
                session_id = str(item.get("session_id") or "") or session_id
                tools = item.get("tools") if isinstance(item.get("tools"), list) else []
                collector.add(
                    "session_start",
                    source=source,
                    session_id=session_id,
                    model=item.get("model"),
                    tools=[str(tool)[:200] for tool in tools],
                    mcp_server_count=len(item.get("mcp_servers") or []),
                    plugin_count=len(item.get("plugins") or []),
                    inferred=False,
                )
                started = True
            elif subtype == "api_retry":
                collector.add(
                    "retry",
                    source=source,
                    attempt=item.get("attempt"),
                    max_retries=item.get("max_retries"),
                    retry_delay_ms=item.get("retry_delay_ms"),
                    error_status=item.get("error_status"),
                    error=item.get("error"),
                    session_id=item.get("session_id"),
                    inferred=False,
                )
            elif subtype in {"compact_boundary", "status"}:
                continue
            else:
                collector.add("unknown", source=source, claude_type=kind, claude_subtype=subtype or None)
            continue

        if kind in {"assistant", "user"}:
            if not started:
                session_id = str(item.get("session_id") or "") or session_id
                collector.add("session_start", source=source, session_id=session_id, inferred=False)
                started = True

            message = item.get("message") if isinstance(item.get("message"), dict) else {}
            parent_tool_use_id = item.get("parent_tool_use_id")
            if kind == "assistant":
                stop_reason = message.get("stop_reason", message.get("stopReason"))
                collector.add(
                    "assistant_message",
                    source=source,
                    response_id=message.get("id"),
                    parent_tool_use_id=parent_tool_use_id,
                    stop_reason=stop_reason,
                    usage=_claude_usage(item),
                    inferred=False,
                )
                if str(stop_reason or "").strip().lower().replace("-", "_") in _REFUSAL_STOP_REASONS:
                    collector.add("refusal", source=source, stop_reason=stop_reason, inferred=False)

            for block in _claude_content_blocks(item):
                block_type = str(block.get("type", "")).strip().lower().replace("-", "_")
                if block_type == "tool_use":
                    tool = str(block.get("name") or "").strip()
                    call_id = str(block.get("id") or "").strip()
                    call_key = call_id or f"{tool}:{len(seen_calls)}"
                    if call_id:
                        tool_names[call_id] = tool
                    if call_key in seen_calls:
                        continue
                    collector.add(
                        "tool_call",
                        source=source,
                        tool=tool or None,
                        call_id=call_id or None,
                        parent_tool_use_id=parent_tool_use_id,
                        inferred=False,
                    )
                    seen_calls.add(call_key)
                    normalized_tool = tool.lower().replace("_", "")
                    if normalized_tool in {"read", "glob", "grep"}:
                        collector.add(
                            "file_read", source=source, tool=tool, call_id=call_id or None, inferred=False
                        )
                    elif normalized_tool in {"write", "edit", "notebookedit"}:
                        collector.add(
                            "file_write", source=source, tool=tool, call_id=call_id or None, inferred=False
                        )
                    elif normalized_tool in {"bash", "powershell"}:
                        collector.add(
                            "terminal", source=source, tool=tool, call_id=call_id or None, inferred=False
                        )
                    if normalized_tool == "agent" and call_key not in seen_subagents:
                        collector.add(
                            "subagent_start",
                            source=source,
                            tool=tool,
                            call_id=call_id or None,
                            parent_tool_use_id=parent_tool_use_id,
                            inferred=False,
                        )
                        seen_subagents.add(call_key)

                elif block_type == "tool_result":
                    call_id = str(block.get("tool_use_id") or "").strip()
                    tool = tool_names.get(call_id, "")
                    result_key = call_id or f"result:{len(seen_results)}"
                    if result_key in seen_results:
                        continue
                    is_error = bool(block.get("is_error"))
                    collector.add(
                        "tool_result",
                        source=source,
                        tool=tool or None,
                        call_id=call_id or None,
                        is_error=is_error,
                        parent_tool_use_id=parent_tool_use_id,
                        inferred=False,
                    )
                    seen_results.add(result_key)
                    if tool.lower().replace("_", "") == "agent" and result_key not in seen_subagent_ends:
                        collector.add(
                            "subagent_end",
                            source=source,
                            tool=tool,
                            call_id=call_id or None,
                            is_error=is_error,
                            parent_tool_use_id=parent_tool_use_id,
                            inferred=False,
                        )
                        seen_subagent_ends.add(result_key)
            continue

        if kind == "result":
            session_id = str(item.get("session_id") or "") or session_id
            usage = _claude_usage(item)
            model_usage = item.get("modelUsage")
            if not isinstance(model_usage, dict):
                model_usage = item.get("model_usage") if isinstance(item.get("model_usage"), dict) else {}
            models = sorted(str(name)[:500] for name in model_usage)
            stop_reason = item.get("stop_reason", item.get("stopReason"))
            is_error = bool(item.get("is_error")) or subtype.startswith("error_")
            if is_error:
                errors = item.get("errors") if isinstance(item.get("errors"), list) else []
                collector.add(
                    "error",
                    source=source,
                    subtype=subtype or None,
                    terminal_reason=item.get("terminal_reason"),
                    api_error_status=item.get("api_error_status"),
                    errors=[str(error)[:1000] for error in errors[:5]],
                    inferred=False,
                )
            if str(stop_reason or "").strip().lower().replace("-", "_") in _REFUSAL_STOP_REASONS:
                collector.add("refusal", source=source, stop_reason=stop_reason, inferred=False)
            collector.add(
                "session_end",
                source=source,
                session_id=session_id,
                subtype=subtype or None,
                terminal_reason=item.get("terminal_reason"),
                stop_reason=stop_reason,
                usage=usage,
                models=models,
                num_turns=item.get("num_turns"),
                is_error=is_error,
                inferred=False,
            )
            ended = True
            continue

        if kind in {"stream_event", "tool_progress", "status", "rate_limit_event", "prompt_suggestion"}:
            continue
        if kind in {"error", "refusal", "refused", "safety_refusal"}:
            collector.add(
                "refusal" if kind in {"refusal", "refused", "safety_refusal"} else "error",
                source=source,
                payload=_compact_payload(item),
                inferred=False,
            )
        elif kind:
            collector.add("unknown", source=source, claude_type=kind, claude_subtype=subtype or None)

    if started and not ended:
        collector.add(
            "session_end",
            source=source,
            session_id=session_id,
            incomplete=True,
            inferred=True,
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
    elif source == "claude":
        events = parse_claude_jsonl(stdout, source=source)
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
