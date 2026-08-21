from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


EVENT_TYPES = {
    "session_start",
    "session_end",
    "assistant_message",
    "tool_call",
    "tool_result",
    "terminal",
    "file_read",
    "file_write",
    "memory_read",
    "memory_write",
    "skill_create",
    "skill_update",
    "subagent_start",
    "subagent_end",
    "error",
    "retry",
    "refusal",
    "server_metrics",
    "human_intervention",
    "unknown",
}


@dataclass
class Event:
    type: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "adapter"
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            self.type = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "timestamp": self.timestamp, "source": self.source, "data": self.data}


class EventCollector:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def add(self, event_type: str, *, source: str = "adapter", **data: Any) -> Event:
        event = Event(event_type, source=source, data=data)
        self.events.append(event)
        return event

    def extend(self, events: list[Event]) -> None:
        self.events.extend(events)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in self.events:
            counts[event.type] = counts.get(event.type, 0) + 1
        return counts
