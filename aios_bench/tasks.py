from __future__ import annotations

import json
from pathlib import Path

from .models import Task


def load_tasks(root: str | Path) -> list[Task]:
    root = Path(root)
    tasks: list[Task] = []
    for path in sorted(root.glob("**/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data:
            tasks.append(
                Task(
                    id=item["id"],
                    category=item["category"],
                    prompt=item["prompt"],
                    mode=item.get("mode", "cold"),
                    tags=tuple(item.get("tags", [])),
                    expected_artifacts=tuple(item.get("expected_artifacts", [])),
                )
            )
    return tasks
