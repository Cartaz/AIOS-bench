from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from typing import Any


_TOOL_HEADING_RE = re.compile(r"Using tool '([^']+)'", re.IGNORECASE)


def _api_key() -> str:
    value = os.environ.get("AIOS_BENCH_AGENTZERO_API_KEY", "").strip()
    if not value:
        raise RuntimeError("AIOS_BENCH_AGENTZERO_API_KEY is required")
    return value


def _base_url() -> str:
    return os.environ.get("AIOS_BENCH_AGENTZERO_URL", "http://127.0.0.1:80").rstrip("/")


def _request_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        _base_url() + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-KEY": _api_key()},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=None) as response:
        body = response.read().decode("utf-8", errors="replace")
    value = json.loads(body)
    if not isinstance(value, dict):
        raise RuntimeError(f"Agent Zero {path} returned a non-object JSON response")
    if value.get("error"):
        raise RuntimeError(f"Agent Zero {path} returned an error")
    return value


def _tool_name(item: dict[str, Any]) -> str | None:
    heading = str(item.get("heading") or "")
    match = _TOOL_HEADING_RE.search(heading)
    if not match:
        return None
    # Agent Zero headings use name[:method].  Keep only the tool identity; the
    # method and arguments can contain task data and are not benchmark telemetry.
    return match.group(1).split(":", 1)[0].strip()[:200] or None


def _event(event_type: str, *, event_id: str | None = None, tool: str | None = None,
           status: str | None = None, error: str | None = None) -> dict[str, Any]:
    event: dict[str, Any] = {"type": event_type, "inferred": False}
    if event_id:
        event["id"] = event_id[:200]
    if tool:
        event["tool"] = tool[:200]
    if status:
        event["status"] = status[:200]
    if error:
        event["error"] = error[:200]
    return event


def normalize_log_items(items: object) -> list[dict[str, Any]]:
    """Project Agent Zero's server-side structured log into bounded events.

    The external API log can contain prompts, tool arguments and tool results.
    None of that content is copied to AIOS-bench.  Only log type, generated id,
    tool identity parsed from Agent Zero's own canonical heading, and terminal
    status are retained.  A ``subagent`` log item is native delegation evidence:
    it is created by ``call_subordinate`` itself, not by model prose.
    """
    if not isinstance(items, list):
        return []

    events: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("type") or "").strip().lower()
        event_id = str(raw.get("id") or raw.get("no") or "").strip() or None

        if kind == "tool":
            tool = _tool_name(raw) or "agentzero_tool"
            events.append(_event("tool_call", event_id=event_id, tool=tool, status="started"))
            events.append(_event("tool_result", event_id=event_id, tool=tool, status="completed"))
        elif kind == "subagent":
            tool = "call_subordinate"
            events.append(_event("tool_call", event_id=event_id, tool=tool, status="started"))
            events.append(_event("subagent_start", event_id=event_id, tool=tool, status="started"))
            events.append(_event("tool_result", event_id=event_id, tool=tool, status="completed"))
            events.append(_event("subagent_end", event_id=event_id, tool=tool, status="completed"))
        elif kind == "browser":
            events.append(_event("tool_call", event_id=event_id, tool="browser", status="started"))
            events.append(_event("tool_result", event_id=event_id, tool="browser", status="completed"))
        elif kind == "code_exe":
            events.append(_event("tool_call", event_id=event_id, tool="code_execution", status="started"))
            events.append(_event("tool_result", event_id=event_id, tool="code_execution", status="completed"))
        elif kind == "error":
            events.append(_event("error", event_id=event_id, error="agentzero_structured_error"))
        elif kind == "response":
            # Presence only. Never copy the assistant response text.
            events.append(_event("assistant", event_id=event_id, status="completed"))

    return events


def _validate_profile() -> tuple[str, str | None]:
    project = os.environ.get("AIOS_BENCH_AGENTZERO_PROJECT", "").strip()
    if not project:
        raise RuntimeError(
            "AIOS_BENCH_AGENTZERO_PROJECT is required; use a dedicated benchmark project"
        )
    isolated = os.environ.get("AIOS_BENCH_AGENTZERO_ISOLATED_PROJECT", "").strip().lower()
    if isolated not in {"1", "true", "yes", "on"}:
        raise RuntimeError(
            "AIOS_BENCH_AGENTZERO_ISOLATED_PROJECT=1 is required after disabling native "
            "memory recall/memorization in the dedicated benchmark project"
        )

    requested = os.environ.get("AIOS_BENCH_REQUESTED_MODEL", "").strip()
    declared = os.environ.get("AIOS_BENCH_AGENTZERO_RESOLVED_MODEL", "").strip()
    if requested and not declared:
        raise RuntimeError(
            "AIOS_BENCH_AGENTZERO_RESOLVED_MODEL is required to bind the remote Agent Zero model"
        )
    if requested and declared != requested:
        raise RuntimeError("Agent Zero resolved-model declaration does not match --model")

    profile = os.environ.get("AIOS_BENCH_AGENTZERO_PROFILE", "").strip() or None
    return project, profile


def run(prompt: str) -> int:
    project, profile = _validate_profile()
    context_id: str | None = None
    cleanup_warning = False
    try:
        payload: dict[str, Any] = {
            "message": prompt,
            "lifetime_hours": 0.25,
            "project_name": project,
        }
        if profile:
            payload["agent_profile"] = profile

        # Deliberately omit context_id: Agent Zero creates a fresh context for
        # every benchmark task, preventing chat/history reuse across attempts.
        result = _request_json("/api_message", payload)
        context_id = str(result.get("context_id") or "").strip()
        if not context_id:
            raise RuntimeError("Agent Zero did not return a context_id")

        log_data = _request_json(
            "/api_log_get",
            {"context_id": context_id, "length": 10000},
        )
        log = log_data.get("log") if isinstance(log_data.get("log"), dict) else {}
        items = log.get("items") if isinstance(log, dict) else []
        for event in normalize_log_items(items):
            print(json.dumps(event, sort_keys=True, separators=(",", ":")))
        return 0
    finally:
        if context_id:
            try:
                _request_json("/api_terminate_chat", {"context_id": context_id})
            except Exception:
                cleanup_warning = True
        if cleanup_warning:
            print("Agent Zero context cleanup warning", file=sys.stderr)


def main() -> int:
    if len(sys.argv) < 2:
        print("missing prompt", file=sys.stderr)
        return 2
    try:
        return run(sys.argv[1])
    except Exception as exc:
        # Keep failure telemetry structured and content-free.  Exception text may
        # contain endpoint details, so stderr exposes only the exception class.
        print(json.dumps(_event("error", error=type(exc).__name__), sort_keys=True))
        print(f"Agent Zero API error: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
