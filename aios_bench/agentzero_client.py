from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

from .agentzero_workspace import EphemeralAgentZeroProject


_TOOL_HEADING_RE = re.compile(r"Using tool '([^']+)'", re.IGNORECASE)
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


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
    # Agent Zero headings use name[:method]. Keep only the tool identity; method,
    # arguments and output can contain task data and are not benchmark telemetry.
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


def _log_item_completed(item: dict[str, Any]) -> bool:
    """Use content presence only as a completion bit; never retain the content."""
    content = item.get("content")
    return isinstance(content, str) and bool(content.strip())


def normalize_log_items(items: object) -> list[dict[str, Any]]:
    """Project Agent Zero's server-side structured log into bounded events.

    The external log can contain prompts, tool arguments and tool results. None
    of that content is copied to AIOS-bench. A native ``subagent`` log item is
    strong start evidence because ``call_subordinate`` creates that type itself.
    Completion events are emitted only when Agent Zero populated the log result;
    an empty/incomplete record is never upgraded to a successful end event.
    """
    if not isinstance(items, list):
        return []

    events: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("type") or "").strip().lower()
        event_id = str(raw.get("id") or raw.get("no") or "").strip() or None
        completed = _log_item_completed(raw)

        if kind == "tool":
            tool = _tool_name(raw) or "agentzero_tool"
            events.append(_event("tool_call", event_id=event_id, tool=tool, status="started"))
            if completed:
                events.append(_event("tool_result", event_id=event_id, tool=tool, status="observed"))
        elif kind == "subagent":
            tool = "call_subordinate"
            events.append(_event("tool_call", event_id=event_id, tool=tool, status="started"))
            events.append(_event("subagent_start", event_id=event_id, tool=tool, status="started"))
            if completed:
                events.append(_event("tool_result", event_id=event_id, tool=tool, status="observed"))
                events.append(_event("subagent_end", event_id=event_id, tool=tool, status="observed"))
        elif kind == "browser":
            events.append(_event("tool_call", event_id=event_id, tool="browser", status="started"))
            if completed:
                events.append(_event("tool_result", event_id=event_id, tool="browser", status="observed"))
        elif kind == "code_exe":
            events.append(_event("tool_call", event_id=event_id, tool="code_execution", status="started"))
            if completed:
                events.append(_event("tool_result", event_id=event_id, tool="code_execution", status="observed"))
        elif kind == "error":
            events.append(_event("error", event_id=event_id, error="agentzero_structured_error"))
        elif kind == "response":
            events.append(_event("assistant", event_id=event_id, status="observed"))

    return events


def _validate_profile() -> tuple[str, str | None, Path, Path]:
    template = os.environ.get("AIOS_BENCH_AGENTZERO_PROJECT", "").strip()
    if not template:
        raise RuntimeError(
            "AIOS_BENCH_AGENTZERO_PROJECT is required; use a neutral template project"
        )
    projects_root_raw = os.environ.get("AIOS_BENCH_AGENTZERO_PROJECTS_ROOT", "").strip()
    if not projects_root_raw:
        raise RuntimeError("AIOS_BENCH_AGENTZERO_PROJECTS_ROOT is required")
    workspace_raw = os.environ.get("AIOS_BENCH_WORKSPACE", "").strip()
    if not workspace_raw:
        raise RuntimeError("AIOS_BENCH_WORKSPACE is required")

    isolated_service = os.environ.get(
        "AIOS_BENCH_AGENTZERO_ISOLATED_SERVICE", ""
    ).strip().lower()
    if isolated_service not in _TRUE_VALUES:
        raise RuntimeError(
            "AIOS_BENCH_AGENTZERO_ISOLATED_SERVICE=1 is required for a dedicated "
            "Agent Zero service/container with no personal host mounts"
        )

    project_memory_isolation = os.environ.get(
        "AIOS_BENCH_AGENTZERO_PROJECT_MEMORY_ISOLATION", ""
    ).strip().lower()
    if project_memory_isolation not in _TRUE_VALUES:
        raise RuntimeError(
            "AIOS_BENCH_AGENTZERO_PROJECT_MEMORY_ISOLATION=1 is required after "
            "verifying Agent Zero project_memory_isolation=true"
        )

    revision = os.environ.get("AIOS_BENCH_AGENTZERO_REVISION", "").strip()
    if not revision:
        raise RuntimeError(
            "AIOS_BENCH_AGENTZERO_REVISION is required; use an Agent Zero release, "
            "commit, or immutable container-image digest"
        )

    requested = os.environ.get("AIOS_BENCH_REQUESTED_MODEL", "").strip()
    declared = os.environ.get("AIOS_BENCH_AGENTZERO_RESOLVED_MODEL", "").strip()
    utility = os.environ.get("AIOS_BENCH_AGENTZERO_UTILITY_MODEL", "").strip()
    if requested and not declared:
        raise RuntimeError(
            "AIOS_BENCH_AGENTZERO_RESOLVED_MODEL is required to bind the remote Agent Zero model"
        )
    if requested and declared != requested:
        raise RuntimeError("Agent Zero resolved-model declaration does not match --model")
    if requested and not utility:
        raise RuntimeError(
            "AIOS_BENCH_AGENTZERO_UTILITY_MODEL is required to attest Agent Zero's utility model"
        )
    if requested and utility != requested:
        raise RuntimeError("Agent Zero utility-model declaration does not match --model")

    profile = os.environ.get("AIOS_BENCH_AGENTZERO_PROFILE", "").strip() or None
    return template, profile, Path(projects_root_raw), Path(workspace_raw)


def run(prompt: str) -> int:
    template, profile, projects_root, workspace = _validate_profile()
    bridge = EphemeralAgentZeroProject(workspace, projects_root, template)
    context_id: str | None = None
    cleanup_warning = False
    try:
        # Every attempt gets a new physical Agent Zero project copied from the
        # neutral metadata-only template. A timed-out/orphaned remote run can
        # therefore never write into the next task's workspace.
        ephemeral_project = bridge.prepare()
        payload: dict[str, Any] = {
            "message": prompt,
            "lifetime_hours": 0.25,
            "project_name": ephemeral_project,
        }
        if profile:
            payload["agent_profile"] = profile

        # Deliberately omit context_id: Agent Zero creates a fresh conversation
        # in the fresh physical project for every benchmark task.
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

        # Stop the completed context before copying artifacts back, removing any
        # chance of a post-response context update racing the local grader.
        try:
            _request_json("/api_terminate_chat", {"context_id": context_id})
            context_id = None
        except Exception:
            cleanup_warning = True

        bridge.sync_back()
        for event in normalize_log_items(items):
            print(json.dumps(event, sort_keys=True, separators=(",", ":")))
        return 0
    finally:
        if context_id:
            try:
                _request_json("/api_terminate_chat", {"context_id": context_id})
            except Exception:
                cleanup_warning = True
        # On normal/error exits remove the ephemeral project. If the outer
        # benchmark SIGKILLs this client on timeout, cleanup cannot run; the
        # unique project name still prevents cross-task contamination.
        bridge.cleanup()
        if cleanup_warning:
            print("Agent Zero context cleanup warning", file=sys.stderr)


def main() -> int:
    if len(sys.argv) < 2:
        print("missing prompt", file=sys.stderr)
        return 2
    try:
        return run(sys.argv[1])
    except Exception as exc:
        # Keep failure telemetry structured and content-free. Exception text may
        # contain endpoint/path details, so stderr exposes only the class.
        print(json.dumps(_event("error", error=type(exc).__name__), sort_keys=True))
        print(f"Agent Zero API error: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
