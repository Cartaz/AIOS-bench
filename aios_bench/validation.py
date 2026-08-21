from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .evaluators import evaluate_artifacts
from .fixtures import materialize_long_horizon_corpus


def _checks(repo_root: Path, task: object) -> list[dict[str, Any]]:
    checks = list(getattr(task, "acceptance", ()) or ())
    spec = repo_root / "benchmarks" / "tasks" / "specs" / f"{getattr(task, 'id')}.json"
    if not checks and spec.is_file():
        checks = json.loads(spec.read_text(encoding="utf-8"))["checks"]
    return checks


def validate_negative_baseline(repo_root: Path, tasks: Iterable[object]) -> dict[str, Any]:
    """Fail if an untouched fixture can already satisfy a deterministic grader."""
    fixture_root = repo_root / "benchmarks" / "fixtures" / "workspace"
    failures: list[dict[str, Any]] = []
    checked = 0
    with tempfile.TemporaryDirectory(prefix="aios-bench-validate-") as temporary:
        root = Path(temporary)
        for task in tasks:
            checks = _checks(repo_root, task)
            task_id = str(getattr(task, "id"))
            if not checks:
                failures.append({"task_id": task_id, "reason": "no deterministic checks"})
                continue
            workspace = root / task_id
            shutil.copytree(fixture_root, workspace)
            if task_id == "long_horizon_001":
                materialize_long_horizon_corpus(workspace)
            evaluation = evaluate_artifacts(
                workspace,
                checks,
                fixture_root=fixture_root,
            )
            checked += 1
            if evaluation["passed"]:
                failures.append({
                    "task_id": task_id,
                    "reason": "untouched fixture passes grader",
                    "acceptance_score": evaluation["acceptance_score"],
                })
    return {
        "schema": "aios-bench/validation/v1",
        "ok": not failures,
        "checked_tasks": checked,
        "failures": failures,
    }
