from __future__ import annotations

import json
import re
from pathlib import Path

from .behavioral_oracles import BehavioralOracleError, validate_behavioral_checks
from .models import Task
from .reference_trajectory import ReferenceTrajectoryError, validate_reference_trajectory


TASK_DIR = "frontier_v3"
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def load_tasks(root: str | Path, task_dir: str = TASK_DIR) -> list[Task]:
    """Load one explicit benchmark catalog.

    Frontier v3 remains the default for backwards compatibility. New suites
    must opt in by passing their catalog directory; silently mixing catalogs is
    intentionally unsupported.
    """
    directory = Path(root) / task_dir
    files = sorted(directory.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"Missing benchmark catalog: {directory}")

    data: list[dict] = []
    for path in files:
        chunk = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(chunk, list):
            raise ValueError(f"Task catalog must contain arrays: {path}")
        for item in chunk:
            if not isinstance(item, dict) or item.get("category") != path.stem:
                raise ValueError(f"Task category must match catalog filename: {path}")
        data.extend(chunk)

    tasks: list[Task] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Task entries must be objects")
        missing = {"id", "category", "prompt", "acceptance"} - item.keys()
        if missing:
            raise ValueError(f"Task is missing required fields: {sorted(missing)}")
        task_id = str(item["id"])
        if not SAFE_ID.fullmatch(task_id):
            raise ValueError(f"Unsafe task id: {task_id!r}")
        if task_id in seen:
            raise ValueError(f"Duplicate task id: {task_id}")
        seen.add(task_id)

        tier = int(item.get("tier", 3))
        if tier not in {3, 4, 5}:
            raise ValueError(f"Frontier benchmark task {item['id']} must be Tier 3-5")
        acceptance = item["acceptance"]
        if (
            not isinstance(acceptance, list)
            or not acceptance
            or not all(isinstance(check, dict) and isinstance(check.get("type"), str) for check in acceptance)
        ):
            raise ValueError(f"Task {task_id} needs valid acceptance checks")
        authoritative = [
            check for check in acceptance
            if isinstance(check, dict) and check.get("type") in {"reference", "parametric_reference"}
        ]
        if len(authoritative) != 1:
            raise ValueError(f"Task {task_id} needs exactly one authoritative oracle")
        oracle = authoritative[0]
        if oracle.get("task_id") != task_id:
            if oracle.get("type") == "reference":
                raise ValueError(f"Task {task_id} needs its matching reference oracle")
            raise ValueError(f"Task {task_id} needs its matching parametric oracle")
        if oracle.get("type") == "parametric_reference" and not oracle.get("family"):
            raise ValueError(f"Task {task_id} parametric oracle needs a family")

        behavioral_raw = item.get("behavioral_acceptance", [])
        if not isinstance(behavioral_raw, list):
            raise ValueError(f"Task {task_id} behavioral_acceptance must be an array")
        try:
            behavioral_acceptance = validate_behavioral_checks(behavioral_raw)
        except BehavioralOracleError as exc:
            raise ValueError(f"Invalid behavioral_acceptance for {task_id}: {exc}") from exc

        try:
            trajectory_reference = validate_reference_trajectory(item.get("trajectory_reference"))
        except ReferenceTrajectoryError as exc:
            raise ValueError(f"Invalid trajectory_reference for {task_id}: {exc}") from exc

        capabilities = item.get("required_capabilities", [])
        if not isinstance(capabilities, list) or not all(isinstance(x, str) and x for x in capabilities):
            raise ValueError(f"Invalid required_capabilities for {task_id}")
        tags = item.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(x, str) for x in tags):
            raise ValueError(f"Invalid tags for {task_id}")
        mode = item.get("mode", "cold")
        if mode not in {"cold", "warm"}:
            raise ValueError(f"Invalid mode for {task_id}: {mode}")
        dependencies = item.get("depends_on", [])
        if (
            not isinstance(dependencies, list)
            or not all(isinstance(x, str) and SAFE_ID.fullmatch(x) for x in dependencies)
        ):
            raise ValueError(f"Invalid dependencies for {task_id}")

        tasks.append(Task(
            id=task_id,
            category=item["category"],
            prompt=item["prompt"],
            mode=mode,
            tier=tier,
            revision=int(item.get("revision", 3)),
            tags=tuple(tags),
            required_capabilities=tuple(capabilities),
            depends_on=tuple(dependencies),
            acceptance=tuple(acceptance),
            behavioral_acceptance=behavioral_acceptance,
            trajectory_reference=trajectory_reference,
        ))

    positions = {task.id: index for index, task in enumerate(tasks)}
    for task in tasks:
        unknown = [dependency for dependency in task.depends_on if dependency not in positions]
        forward = [
            dependency for dependency in task.depends_on
            if positions.get(dependency, -1) >= positions[task.id]
        ]
        if unknown or forward:
            raise ValueError(f"Task {task.id} has invalid dependency order: {unknown or forward}")
    return tasks
