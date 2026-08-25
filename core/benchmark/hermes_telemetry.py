from __future__ import annotations

import json
from typing import Any, Mapping

from .events import Event, EventCollector


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def parse_hermes_usage_report(text: str, *, source: str = "hermes") -> list[Event]:
    """Normalize Hermes ``--usage-file`` JSON without trusting response prose.

    The one-shot usage report is a harness-produced accounting sidecar. It is
    useful for model/provider identity and token accounting, but it is not a
    tool-event stream: it must never be interpreted as structured delegation
    evidence. The benchmark reads and removes the sidecar before artifact
    grading so it cannot become part of the task result.
    """
    try:
        item = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(item, Mapping):
        return []

    collector = EventCollector()
    session_id = item.get("session_id")
    model = item.get("model")
    provider = item.get("provider")
    usage = {
        "input": _integer(item.get("input_tokens")),
        "output": _integer(item.get("output_tokens")),
        "reasoning": _integer(item.get("reasoning_tokens")),
        "total": _integer(item.get("total_tokens")),
    }
    if usage["total"] <= 0 and (usage["input"] or usage["output"] or usage["reasoning"]):
        usage["total"] = usage["input"] + usage["output"] + usage["reasoning"]

    collector.add(
        "session_start",
        source=source,
        session_id=str(session_id) if session_id is not None else None,
        model=str(model) if model is not None else None,
        provider=str(provider) if provider is not None else None,
        inferred=False,
    )
    if bool(item.get("failed")):
        collector.add("error", source=source, kind="harness_reported_failure", inferred=False)
    collector.add(
        "session_end",
        source=source,
        session_id=str(session_id) if session_id is not None else None,
        model=str(model) if model is not None else None,
        provider=str(provider) if provider is not None else None,
        completed=bool(item.get("completed")),
        failed=bool(item.get("failed")),
        api_calls=_integer(item.get("api_calls")),
        usage=usage,
        inferred=False,
    )
    return collector.events
