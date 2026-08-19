from dataclasses import dataclass, field
from typing import Any


@dataclass
class Task:
    id: str
    category: str
    prompt: str
    mode: str = "cold"
    fixture: str | None = None
    expected: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class Trajectory:
    task_id: str
    agent: str
    success: bool
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
    subagents: int = 0
    proportionality: float | None = None
    notes: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Trajectory":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}
