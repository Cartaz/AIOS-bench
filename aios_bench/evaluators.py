from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable


class EvaluationError(ValueError):
    pass


def file_exists(workspace: Path, relative_path: str) -> bool:
    return (workspace / relative_path).is_file()


def file_contains(workspace: Path, relative_path: str, text: str) -> bool:
    path = workspace / relative_path
    return path.is_file() and text in path.read_text(encoding="utf-8")


def file_sha256(workspace: Path, relative_path: str) -> str:
    path = workspace / relative_path
    if not path.is_file():
        raise EvaluationError(f"missing artifact: {relative_path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_artifacts(workspace: Path, checks: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for check in checks:
        kind = check["type"]
        path = check.get("path", "")
        if kind == "exists":
            passed = file_exists(workspace, path)
        elif kind == "contains":
            passed = file_contains(workspace, path, check["text"])
        elif kind == "sha256":
            passed = file_sha256(workspace, path) == check["sha256"]
        else:
            raise EvaluationError(f"unknown check type: {kind}")
        results.append({"check": check, "passed": passed})
    passed = sum(r["passed"] for r in results)
    return {
        "passed": passed == len(results),
        "checks_passed": passed,
        "checks_total": len(results),
        "results": results,
    }


def evaluate_json(workspace: Path, spec_path: str | Path) -> dict[str, Any]:
    spec_file = Path(spec_path)
    if not spec_file.is_absolute():
        spec_file = workspace / spec_file
    spec = json.loads(spec_file.read_text(encoding="utf-8"))
    return evaluate_artifacts(workspace, spec["checks"])


def registry() -> dict[str, Callable[..., dict[str, Any]]]:
    return {"artifacts": evaluate_artifacts, "json": evaluate_json}
