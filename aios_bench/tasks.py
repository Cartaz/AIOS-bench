from __future__ import annotations

import json
from pathlib import Path

from .models import Task


TASK_FILE = "frontier_v2.json"


def load_tasks(root: str | Path) -> list[Task]:
    root = Path(root)
    path = root / TASK_FILE
    if not path.is_file():
        raise FileNotFoundError(f"Missing benchmark catalog: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Task catalog must contain a JSON array: {path}")
    tasks: list[Task] = []
    for item in data:
        tier = int(item.get("tier", 3))
        if tier not in {3, 4, 5}:
            raise ValueError(f"Frontier benchmark task {item['id']} must be Tier 3-5")
        tasks.append(Task(
            id=item["id"], category=item["category"], prompt=item["prompt"],
            mode=item.get("mode", "cold"), tier=tier, revision=int(item.get("revision", 2)),
            tags=tuple(item.get("tags", [])), expected_artifacts=tuple(item.get("expected_artifacts", [])),
            acceptance=tuple(item.get("acceptance", [])),
        ))
    return tasks
