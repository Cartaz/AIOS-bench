from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any, Iterable


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _matches_suite(row: dict[str, Any], suite: str | None, suite_revision: str | None) -> bool:
    if suite is not None and str(row.get("suite")) != suite:
        return False
    if suite_revision is not None and str(row.get("suite_revision")) != suite_revision:
        return False
    return True


def _reliable_events(row: dict[str, Any]) -> list[dict[str, Any]]:
    events = row.get("events")
    if not isinstance(events, list):
        return []
    reliable: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        data = event.get("data")
        if isinstance(data, dict) and data.get("inferred") is True:
            continue
        reliable.append(event)
    return reliable


def task_behavior(row: dict[str, Any]) -> dict[str, Any]:
    """Derive descriptive behavior metrics from canonical, non-inferred events.

    Generic telemetry intentionally does not guess whether an action was useful,
    destructive, or a recovery. Those semantics require task-specific,
    deterministic evidence and belong in benchmark oracles.
    """
    events = _reliable_events(row)
    counts: dict[str, int] = defaultdict(int)
    tools: list[str] = []
    tool_errors = 0
    assistant_turns = 0

    for event in events:
        kind = str(event.get("type") or "unknown")
        counts[kind] += 1
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if kind == "tool_call":
            tool = str(data.get("tool") or data.get("name") or "unknown")
            tools.append(tool)
        elif kind == "tool_result" and bool(data.get("is_error")):
            tool_errors += 1
        elif kind == "assistant_message" and bool(data.get("turn") or data.get("step")):
            assistant_turns += 1

    repeated_tool_calls = sum(left == right for left, right in zip(tools, tools[1:]))
    duration = _number(row.get("duration_seconds"))
    output_tokens = _number(row.get("output_tokens"))

    return {
        "telemetry_available": bool(events),
        "reliable_events": len(events),
        "assistant_turns": assistant_turns,
        "tool_calls": len(tools),
        "unique_tools": len(set(tools)),
        "consecutive_repeated_tool_calls": repeated_tool_calls,
        "tool_errors": tool_errors,
        "retries": counts.get("retry", 0),
        "file_reads": counts.get("file_read", 0),
        "file_writes": counts.get("file_write", 0),
        "subagent_starts": counts.get("subagent_start", 0),
        "refusals": counts.get("refusal", 0),
        "duration_seconds": duration,
        "output_tokens": output_tokens,
        "tool_calls_per_minute": len(tools) * 60.0 / duration if duration and duration > 0 else None,
        "output_tokens_per_tool_call": output_tokens / len(tools) if output_tokens is not None and tools else None,
        "scope": "canonical_non_inferred_events",
        "affects_score": False,
    }


def _mean(items: list[dict[str, Any]], field: str) -> float | None:
    values = [_number(item.get(field)) for item in items]
    clean = [value for value in values if value is not None]
    return statistics.fmean(clean) if clean else None


def behavior_efficiency_groups(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate deterministic trajectory telemetry by execution profile."""
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("status") == "unsupported" or row.get("comparable") is False:
            continue
        if not _matches_suite(row, suite, suite_revision):
            continue
        behavior = row.get("agent_behavior")
        if not isinstance(behavior, dict):
            behavior = task_behavior(row)
        if not behavior.get("telemetry_available"):
            continue
        key = (
            str(row.get("harness", row.get("agent", "unknown"))),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
            str(row.get("execution_fingerprint", "unreported")),
        )
        grouped[key].append(behavior)

    result: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        result.append({
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "execution_fingerprint": key[4],
            "tasks_with_behavior_telemetry": len(items),
            "mean_assistant_turns": _mean(items, "assistant_turns"),
            "mean_tool_calls": _mean(items, "tool_calls"),
            "mean_unique_tools": _mean(items, "unique_tools"),
            "mean_consecutive_repeated_tool_calls": _mean(items, "consecutive_repeated_tool_calls"),
            "mean_tool_errors": _mean(items, "tool_errors"),
            "mean_retries": _mean(items, "retries"),
            "mean_file_reads": _mean(items, "file_reads"),
            "mean_file_writes": _mean(items, "file_writes"),
            "mean_subagent_starts": _mean(items, "subagent_starts"),
            "mean_duration_seconds": _mean(items, "duration_seconds"),
            "mean_tool_calls_per_minute": _mean(items, "tool_calls_per_minute"),
            "mean_output_tokens_per_tool_call": _mean(items, "output_tokens_per_tool_call"),
            "total_tool_errors": int(sum(int(item.get("tool_errors", 0) or 0) for item in items)),
            "total_retries": int(sum(int(item.get("retries", 0) or 0) for item in items)),
            "total_refusals": int(sum(int(item.get("refusals", 0) or 0) for item in items)),
            "scope": "canonical_non_inferred_events",
            "affects_score": False,
        })
    return result
