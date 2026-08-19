from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

@dataclass
class Task:
    id: str
    category: str
    prompt: str
    mode: str = "cold"
    timeout_s: int = 300
    evaluator: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

@dataclass
class Trajectory:
    agent: str
    task_id: str
    success: bool
    duration_s: float = 0.0
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
    artifacts: list[str] = field(default_factory=list)
    notes: str = ""


def load_tasks(path: str | Path = ROOT / "benchmark" / "tasks" / "pilot.json") -> list[Task]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Task(**item) for item in data["tasks"]]


def load_trajectory(path: str | Path) -> list[Trajectory]:
    out: list[Trajectory] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(Trajectory(**json.loads(line)))
    return out
