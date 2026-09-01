from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from .parametric import evaluate_variant
from .reference_checks import check_task


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
    return path.is_file() and text.lower() in path.read_text(
        encoding="utf-8", errors="replace"
    ).lower()


def file_sha256(workspace: Path, relative_path: str) -> str:
    path = _safe_path(workspace, relative_path)
    if not path.is_file():
        raise EvaluationError(f"missing artifact: {relative_path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_sha256(fixture_root: Path, relative_path: str) -> str:
    path = _safe_path(fixture_root, relative_path)
    if not path.is_file():
        raise EvaluationError(f"missing fixture baseline: {relative_path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_check_command(workspace: Path, command: str | list[str], timeout: float = 30.0):
    args = shlex.split(command) if isinstance(command, str) else [str(item) for item in command]
    if not args:
        raise EvaluationError("check command must not be empty")
    process = subprocess.run(
        args,
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return process.returncode == 0, (process.stdout + "\n" + process.stderr).strip()[-4000:]


def _load_parametric_oracle(run_dir: Path | None, task_id: str) -> dict[str, Any]:
    if run_dir is None:
        raise EvaluationError("run_dir is required for parametric reference checks")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", task_id):
        raise EvaluationError(f"unsafe parametric task id: {task_id!r}")
    path = run_dir / "oracles" / f"{task_id}.json"
    if not path.is_file():
        raise EvaluationError(f"missing parametric oracle: {task_id}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvaluationError(f"invalid parametric oracle: {task_id}")
    return value


def _delegation_fields(event: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return normalized structural delegation fields without retaining payload text."""
    data = event.get("data")
    if not isinstance(data, Mapping):
        return {}
    payload = data.get("payload")
    if isinstance(payload, Mapping):
        return payload
    return data


def _delegation_event_id(fields: Mapping[str, Any]) -> str | None:
    for key in ("call_id", "id"):
        value = fields.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _structured_delegation_check(
    events: list[dict[str, Any]],
    *,
    min_starts: int,
    min_completed: int,
    require_unique_ids: bool,
) -> tuple[bool, str]:
    if min_starts <= 0 or min_completed <= 0:
        raise EvaluationError("structured delegation minima must be positive")

    strong_starts: list[str | None] = []
    strong_ends: list[str | None] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        event_type = event.get("type")
        if event_type not in {"subagent_start", "subagent_end"}:
            continue
        fields = _delegation_fields(event)
        if fields.get("inferred") is not False:
            continue
        event_id = _delegation_event_id(fields)
        if event_type == "subagent_start":
            strong_starts.append(event_id)
            continue
        status = str(fields.get("status") or "").strip().lower()
        if fields.get("is_error") is True or status in {
            "error", "failed", "failure", "cancelled", "canceled",
        }:
            continue
        strong_ends.append(event_id)

    if require_unique_ids:
        start_ids = {event_id for event_id in strong_starts if event_id is not None}
        end_ids = {event_id for event_id in strong_ends if event_id is not None}
        completed_ids = start_ids.intersection(end_ids)
        passed = len(start_ids) >= min_starts and len(completed_ids) >= min_completed
        detail = (
            f"structured starts={len(start_ids)}, completed={len(completed_ids)}, "
            f"required_starts={min_starts}, required_completed={min_completed}"
        )
        return passed, detail

    starts = len(strong_starts)
    completed = len(strong_ends)
    passed = starts >= min_starts and completed >= min_completed
    detail = (
        f"structured starts={starts}, completed={completed}, "
        f"required_starts={min_starts}, required_completed={min_completed}"
    )
    return passed, detail


def evaluate_artifacts(
    workspace: Path,
    checks: list[dict[str, Any]],
    run_dir: Path | None = None,
    events: list[dict[str, Any]] | None = None,
    fixture_root: Path | None = None,
) -> dict[str, Any]:
    results = []
    for check in checks:
        kind = check["type"]
        path = check.get("path", "")
        detail = ""
        failure_kind: str | None = None
        metrics: dict[str, Any] = {}
        credit: float | None = None
        try:
            if kind == "exists":
                passed = file_exists(workspace, path)
            elif kind == "contains":
                passed = file_contains(workspace, path, check["text"])
            elif kind == "contains_any":
                passed = any(file_contains(workspace, path, text) for text in check["texts"])
            elif kind == "regex":
                candidate = _safe_path(workspace, path)
                passed = candidate.is_file() and re.search(
                    check["pattern"],
                    candidate.read_text(encoding="utf-8", errors="replace"),
                    re.MULTILINE,
                ) is not None
            elif kind == "min_lines":
                candidate = _safe_path(workspace, path)
                passed = candidate.is_file() and len(
                    candidate.read_text(encoding="utf-8", errors="replace").splitlines()
                ) >= int(check["lines"])
            elif kind == "json_valid":
                candidate = _safe_path(workspace, path)
                if not candidate.is_file():
                    raise ValueError("missing file")
                json.loads(candidate.read_text(encoding="utf-8"))
                passed = True
            elif kind == "sha256":
                passed = file_sha256(workspace, path) == check["sha256"]
            elif kind == "unchanged":
                if fixture_root is None:
                    root = os.environ.get("AIOS_BENCH_FIXTURE_ROOT")
                    if not root:
                        raise EvaluationError("fixture_root is required for unchanged checks")
                    fixture_root = Path(root)
                passed = file_sha256(workspace, path) == _fixture_sha256(fixture_root, path)
            elif kind == "command":
                passed, detail = _run_check_command(
                    workspace, check["command"], float(check.get("timeout", 30))
                )
            elif kind == "structured_delegation":
                passed, detail = _structured_delegation_check(
                    events or [],
                    min_starts=int(check.get("min_starts", 1)),
                    min_completed=int(check.get("min_completed", 1)),
                    require_unique_ids=bool(check.get("require_unique_ids", False)),
                )
            elif kind == "reference":
                reference_result = check_task(
                    check["task_id"],
                    workspace,
                    fixture_root or Path(os.environ["AIOS_BENCH_FIXTURE_ROOT"]),
                    run_dir,
                    events=events or [],
                )
                if reference_result is None:
                    raise EvaluationError(
                        f"reference check returned no result for task: {check['task_id']}"
                    )
                passed, detail = reference_result
            elif kind == "parametric_reference":
                task_id = str(check["task_id"])
                family = str(check["family"])
                oracle = _load_parametric_oracle(run_dir, task_id)
                if oracle.get("family") != family:
                    raise EvaluationError("parametric family/oracle mismatch")
                grade = evaluate_variant(
                    family,
                    workspace,
                    oracle,
                    run_dir=run_dir,
                    task_id=task_id,
                )
                passed = grade.passed
                detail = grade.detail
                failure_kind = grade.failure_kind
                credit = grade.score
                metrics = dict(grade.metrics)
            elif kind == "max_files":
                candidate = _safe_path(workspace, path or ".")
                count = sum(1 for item in candidate.rglob("*") if item.is_file()) if candidate.exists() else 0
                passed = count <= int(check["max"])
                detail = f"file_count={count}"
            else:
                raise EvaluationError(f"unknown check type: {kind}")
        except Exception as exc:
            # Agent-authored artifacts are untrusted input to the oracle. A
            # malformed artifact fails its check; it must not abort the suite.
            passed = False
            detail = f"{type(exc).__name__}: {exc}"
            credit = 0.0
            metrics = {}
        if credit is None:
            credit = 1.0 if passed else 0.0
        results.append({
            "check": check,
            "passed": passed,
            "weight": float(check.get("weight", 1.0)),
            "credit": float(credit),
            "detail": detail,
            "failure_kind": failure_kind,
            "metrics": metrics,
        })

    total = sum(result["weight"] for result in results) or 1.0
    earned = sum(result["weight"] * result["credit"] for result in results)
    fatal = any(
        not result["passed"] and result["check"].get("fatal", False)
        for result in results
    )
    score = earned / total
    failure_kind = next(
        (
            str(result["failure_kind"])
            for result in results
            if not result["passed"] and result.get("failure_kind")
        ),
        None,
    )
    parametric_metrics = {
        str(result["check"]["family"]): result["metrics"]
        for result in results
        if result["check"].get("type") == "parametric_reference" and result["metrics"]
    }
    return {
        "passed": not fatal and score >= 0.80,
        "acceptance_score": score,
        "checks_passed": sum(result["passed"] for result in results),
        "checks_total": len(results),
        "failure_kind": failure_kind,
        "metrics": parametric_metrics,
        "results": results,
    }


def evaluate_json(
    workspace: Path,
    spec_path: str | Path,
    run_dir: Path | None = None,
    fixture_root: Path | None = None,
) -> dict[str, Any]:
    path = Path(spec_path)
    path = path if path.is_absolute() else workspace / path
    return evaluate_artifacts(
        workspace,
        json.loads(path.read_text(encoding="utf-8"))["checks"],
        run_dir=run_dir,
        fixture_root=fixture_root,
    )


def registry() -> dict[str, Callable[..., dict[str, Any]]]:
    return {"artifacts": evaluate_artifacts, "json": evaluate_json}
