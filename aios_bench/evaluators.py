from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable


class EvaluationError(ValueError):
    pass


def _safe_path(workspace: Path, relative_path: str) -> Path:
    path = (workspace / relative_path).resolve()
    root = workspace.resolve()
    if root not in path.parents and path != root:
        raise EvaluationError(f"path escapes workspace: {relative_path}")
    return path


def file_exists(workspace: Path, relative_path: str) -> bool:
    return _safe_path(workspace, relative_path).is_file()


def file_contains(workspace: Path, relative_path: str, text: str) -> bool:
    path = _safe_path(workspace, relative_path)
    return path.is_file() and text in path.read_text(encoding="utf-8", errors="replace")


def file_sha256(workspace: Path, relative_path: str) -> str:
    path = _safe_path(workspace, relative_path)
    if not path.is_file():
        raise EvaluationError(f"missing artifact: {relative_path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_sha256(workspace: Path, relative_path: str) -> str:
    # The runner copies the canonical fixture to the task workspace. This lets
    # an acceptance check prove that a protected input was not modified.
    source = workspace.parent.parent.parent.parent / "fixtures" / "workspace" / relative_path
    if not source.is_file():
        raise EvaluationError(f"missing fixture baseline: {relative_path}")
    return hashlib.sha256(source.read_bytes()).hexdigest()


def _run_check_command(workspace: Path, command: str, timeout: float = 30.0) -> tuple[bool, str]:
    proc = subprocess.run(command, cwd=workspace, shell=True, text=True,
                          capture_output=True, timeout=timeout, check=False)
    detail = (proc.stdout + "\n" + proc.stderr).strip()[-4000:]
    return proc.returncode == 0, detail


def evaluate_artifacts(workspace: Path, checks: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for check in checks:
        kind = check["type"]
        path = check.get("path", "")
        detail = ""
        try:
            if kind == "exists":
                passed = file_exists(workspace, path)
            elif kind == "contains":
                passed = file_contains(workspace, path, check["text"])
            elif kind == "contains_any":
                passed = any(file_contains(workspace, path, text) for text in check["texts"])
            elif kind == "regex":
                target = _safe_path(workspace, path)
                passed = target.is_file() and re.search(check["pattern"], target.read_text(encoding="utf-8", errors="replace"), re.MULTILINE) is not None
            elif kind == "min_lines":
                target = _safe_path(workspace, path)
                passed = target.is_file() and len(target.read_text(encoding="utf-8", errors="replace").splitlines()) >= int(check["lines"])
            elif kind == "json_valid":
                target = _safe_path(workspace, path)
                if not target.is_file():
                    passed = False
                else:
                    json.loads(target.read_text(encoding="utf-8"))
                    passed = True
            elif kind == "sha256":
                passed = file_sha256(workspace, path) == check["sha256"]
            elif kind == "unchanged":
                passed = file_sha256(workspace, path) == _snapshot_sha256(workspace, path)
            elif kind == "command":
                passed, detail = _run_check_command(workspace, check["command"], float(check.get("timeout", 30)))
            elif kind == "max_files":
                target = _safe_path(workspace, path or ".")
                count = sum(1 for p in target.rglob("*") if p.is_file()) if target.exists() else 0
                passed = count <= int(check["max"])
                detail = f"file_count={count}"
            else:
                raise EvaluationError(f"unknown check type: {kind}")
        except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
            passed = False
            detail = str(exc)
        results.append({"check": check, "passed": passed, "weight": float(check.get("weight", 1.0)), "detail": detail})

    total_weight = sum(r["weight"] for r in results) or 1.0
    earned = sum(r["weight"] for r in results if r["passed"])
    fatal_failed = any(not r["passed"] and r["check"].get("fatal", False) for r in results)
    acceptance_score = earned / total_weight
    return {
        "passed": not fatal_failed and acceptance_score >= 0.80,
        "acceptance_score": acceptance_score,
        "checks_passed": sum(r["passed"] for r in results),
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
