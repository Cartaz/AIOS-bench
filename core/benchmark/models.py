from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Task:
    id: str
    category: str
    prompt: str
    mode: str = "cold"
    tier: int = 3
    revision: int = 1
    tags: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    acceptance: tuple[dict[str, Any], ...] = ()
    setup: tuple[str, ...] = ()


@dataclass
class Trajectory:
    agent: str
    task_id: str
    success: bool = False
    duration_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    errors: int = 0
    retries: int = 0
    human_interventions: int = 0
    files_read: int = 0
    files_written: int = 0
    memory_reads: int = 0
    memory_writes: int = 0
    skills_created: int = 0
    telemetry_available: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)
    evaluation_score: float | None = None

    def apply_events(self, events: list[dict[str, Any]]) -> None:
        self.events = events
        self.telemetry_available = bool(events)
        counts: dict[str, int] = {}
        input_tokens = output_tokens = 0
        for event in events:
            kind = event.get("type", "unknown")
            counts[kind] = counts.get(kind, 0) + 1
            data = event.get("data") or {}
            usage = data.get("usage") or {}
            input_tokens = max(input_tokens, int(usage.get("input", 0) or 0))
            output_tokens = max(output_tokens, int(usage.get("output", 0) or 0))
        self.input_tokens = max(self.input_tokens, input_tokens)
        self.output_tokens = max(self.output_tokens, output_tokens)
        self.tool_calls = counts.get("tool_call", 0)
        reliable_errors = sum(
            event.get("type") == "error"
            and not (event.get("data") or {}).get("inferred", False)
            for event in events
        )
        self.errors = max(self.errors, reliable_errors)
        self.retries = counts.get("retry", 0)
        self.human_interventions = counts.get("human_intervention", 0)
        self.files_read = counts.get("file_read", 0)
        self.files_written = counts.get("file_write", 0)
        self.memory_reads = counts.get("memory_read", 0)
        self.memory_writes = counts.get("memory_write", 0)
        self.skills_created = counts.get("skill_create", 0) + counts.get("skill_update", 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "task_id": self.task_id,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "retries": self.retries,
            "human_interventions": self.human_interventions,
            "files_read": self.files_read,
            "files_written": self.files_written,
            "memory_reads": self.memory_reads,
            "memory_writes": self.memory_writes,
            "skills_created": self.skills_created,
            "telemetry_available": self.telemetry_available,
            "evaluation_score": self.evaluation_score,
            "events": self.events,
        }
