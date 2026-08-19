from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _artifact_exists(root: Path, value: str) -> bool:
    return (root / value).exists()


def evaluate(task: dict[str, Any], trajectory: dict[str, Any], workspace: str | Path) -> dict[str, Any]:
    """Evaluate deterministic checks plus trajectory-level quality metrics.

    Deterministic evaluators never inspect private model reasoning. Subjective tasks
    may use `human_judge` and are reported separately rather than fabricated.
    """
    root = Path(workspace)
    ev = task.get("evaluator", {})
    kind = ev.get("type", "trajectory")
    passed = True
    details: dict[str, Any] = {}

    if kind == "trajectory":
        passed = bool(trajectory.get("success"))
    elif kind == "file_exists":
        passed = all(_artifact_exists(root, p) for p in ev.get("paths", []))
        details["paths"] = ev.get("paths", [])
    elif kind == "file_contains":
        checks = []
        for item in ev.get("checks", []):
            p = root / item["path"]
            ok = p.exists() and item["text"] in p.read_text(encoding="utf-8")
            checks.append(ok)
        passed = all(checks)
        details["checks_passed"] = sum(checks)
        details["checks_total"] = len(checks)
    elif kind == "json_value":
        checks = []
        for item in ev.get("checks", []):
            p = root / item["path"]
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
                value = obj
                for part in item["key"].split("."):
                    value = value[part]
                checks.append(value == item["expected"])
            except (OSError, ValueError, KeyError, TypeError):
                checks.append(False)
        passed = all(checks)
        details["checks_passed"] = sum(checks)
        details["checks_total"] = len(checks)
    elif kind == "command_exit":
        # The adapter records command results in events. This evaluator checks
        # for an event with the requested command and a zero exit code.
        target = ev.get("command")
        matches = [e for e in trajectory.get("events", []) if e.get("type") == "command" and e.get("command") == target]
        passed = any(e.get("exit_code") == 0 for e in matches)
        details["matching_events"] = len(matches)
    elif kind == "human_judge":
        passed = bool(trajectory.get("success"))
        details["requires_human_review"] = True
    else:
        raise ValueError(f"Unknown evaluator type: {kind}")

    efficiency = max(0.0, 1.0 - min(1.0, trajectory.get("errors", 0) / 5.0))
    intervention = max(0.0, 1.0 - min(1.0, trajectory.get("human_interventions", 0) / 3.0))
    proportionality = 1.0 / max(1.0, trajectory.get("tool_calls", 1) / 4.0)
    quality = (float(passed) * 0.70) + (efficiency * 0.15) + (intervention * 0.10) + (proportionality * 0.05)

    return {
        "task_id": task["id"],
        "category": task["category"],
        "passed": passed,
        "quality_score": round(quality * 100, 2),
        "details": details,
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"tasks": 0, "score": 0.0}
    categories: dict[str, list[float]] = {}
    for r in results:
        categories.setdefault(r["category"], []).append(r["quality_score"])
    by_category = {k: round(sum(v) / len(v), 2) for k, v in categories.items()}
    return {
        "tasks": len(results),
        "passed": sum(bool(r["passed"]) for r in results),
        "score": round(sum(r["quality_score"] for r in results) / len(results), 2),
        "by_category": by_category,
    }
