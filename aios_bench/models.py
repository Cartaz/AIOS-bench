from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Task:
    id: str
    category: str
    prompt: str
    mode: str = "cold"
    tags: tuple[str, ...] = ()
    expected_artifacts: tuple[str, ...] = ()


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
    events: list[dict[str, Any]] = field(default_factory=list)

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
            "events": self.events,
        }
