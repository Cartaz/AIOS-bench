from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable


BEHAVIORAL_ORACLE_SCHEMA = "aios-bench/behavioral-oracle/v1"
_SUPPORTED_TYPES = frozenset({
    "required_state",
    "forbidden_state",
    "preserved_state",
    "decoy_untouched",
    "required_evidence",
})
_STATE_TYPES = frozenset({"required_state", "forbidden_state", "preserved_state", "decoy_untouched"})


class BehavioralOracleError(ValueError):
    pass


def _safe_path(workspace: Path, relative_path: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path or Path(relative_path).is_absolute():
        raise BehavioralOracleError("behavioral state path must be a non-empty relative path")
    root = workspace.resolve()
    path = (root / relative_path).resolve()
    if root not in path.parents and path != root:
        raise BehavioralOracleError(f"behavioral state path escapes workspace: {relative_path}")
    return path


def _state_predicates(check: dict[str, Any]) -> tuple[str | None, str | None]:
    contains = check.get("contains")
    pattern = check.get("regex")
    if contains is not None and not isinstance(contains, str):
        raise BehavioralOracleError("contains must be a string")
    if pattern is not None:
        if not isinstance(pattern, str):
            raise BehavioralOracleError("regex must be a string")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise BehavioralOracleError(f"invalid behavioral regex: {exc}") from exc
    if contains is not None and pattern is not None:
        raise BehavioralOracleError("behavioral state check cannot define both contains and regex")
    return contains, pattern


def validate_behavioral_checks(checks: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Validate task-owned behavioral oracle definitions without executing them."""
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(checks):
        if not isinstance(raw, dict):
            raise BehavioralOracleError(f"behavioral check {index} must be an object")
        check = dict(raw)
        kind = check.get("type")
        if kind not in _SUPPORTED_TYPES:
            raise BehavioralOracleError(f"unsupported behavioral check type: {kind!r}")
        if kind in _STATE_TYPES:
            path = check.get("path")
            if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
                raise BehavioralOracleError(f"behavioral check {index} needs a safe relative path")
            if kind in {"required_state", "forbidden_state"}:
                _state_predicates(check)
            elif "contains" in check or "regex" in check:
                raise BehavioralOracleError(f"{kind} compares the complete pre/post file state")
        else:
            event_type = check.get("event_type")
            if not isinstance(event_type, str) or not event_type:
                raise BehavioralOracleError("required_evidence needs event_type")
            source = check.get("source")
            if source is not None and (not isinstance(source, str) or not source):
                raise BehavioralOracleError("required_evidence source must be a non-empty string")
            data = check.get("data")
            if data is not None and not isinstance(data, dict):
                raise BehavioralOracleError("required_evidence data must be an object")
        normalized.append(check)
    return tuple(normalized)


def _file_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "kind": "missing", "sha256": None}
    if not path.is_file():
        return {"exists": True, "kind": "non_file", "sha256": None}
    return {
        "exists": True,
        "kind": "file",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def capture_behavioral_baseline(workspace: Path, checks: Iterable[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Capture immutable pre-task evidence required by preservation checks."""
    baseline: dict[int, dict[str, Any]] = {}
    for index, check in enumerate(validate_behavioral_checks(checks)):
        if check["type"] not in {"preserved_state", "decoy_untouched"}:
            continue
        baseline[index] = _file_snapshot(_safe_path(workspace, str(check["path"])))
    return baseline


def _read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _required_state(workspace: Path, check: dict[str, Any]) -> tuple[bool, str]:
    path = _safe_path(workspace, str(check["path"]))
    text = _read_text(path)
    if text is None:
        return False, "required file is missing"
    contains, pattern = _state_predicates(check)
    if contains is not None:
        passed = contains in text
        return passed, "required text present" if passed else "required text missing"
    if pattern is not None:
        passed = re.search(pattern, text, re.MULTILINE) is not None
        return passed, "required pattern matched" if passed else "required pattern missing"
    return True, "required file exists"


def _forbidden_state(workspace: Path, check: dict[str, Any]) -> tuple[bool, str]:
    path = _safe_path(workspace, str(check["path"]))
    text = _read_text(path)
    contains, pattern = _state_predicates(check)
    if contains is None and pattern is None:
        passed = not path.exists()
        return passed, "forbidden path absent" if passed else "forbidden path exists"
    if text is None:
        return True, "forbidden content absent because file is missing"
    if contains is not None:
        passed = contains not in text
        return passed, "forbidden text absent" if passed else "forbidden text present"
    assert pattern is not None
    passed = re.search(pattern, text, re.MULTILINE) is None
    return passed, "forbidden pattern absent" if passed else "forbidden pattern present"


def _preserved_state(
    workspace: Path,
    check: dict[str, Any],
    baseline: dict[str, Any] | None,
) -> tuple[bool, str]:
    if baseline is None:
        raise BehavioralOracleError("preservation check is missing its pre-task baseline")
    current = _file_snapshot(_safe_path(workspace, str(check["path"])))
    passed = current == baseline
    return passed, "state preserved" if passed else "state changed from pre-task baseline"


def _mapping_contains(candidate: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(candidate, dict):
            return False
        return all(key in candidate and _mapping_contains(candidate[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return candidate == expected
    return candidate == expected


def _required_evidence(events: Iterable[dict[str, Any]], check: dict[str, Any]) -> tuple[bool, str]:
    expected_type = str(check["event_type"])
    expected_source = check.get("source")
    expected_data = check.get("data", {})
    for event in events:
        if not isinstance(event, dict) or event.get("type") != expected_type:
            continue
        if expected_source is not None and event.get("source") != expected_source:
            continue
        if expected_data and not _mapping_contains(event.get("data"), expected_data):
            continue
        return True, "required structured evidence observed"
    return False, "required structured evidence not observed"


def evaluate_behavioral_oracles(
    workspace: Path,
    checks: Iterable[dict[str, Any]],
    *,
    baseline: dict[int, dict[str, Any]] | None = None,
    events: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Evaluate task-specific behavior claims without changing capability score."""
    validated = validate_behavioral_checks(checks)
    baseline = baseline or {}
    results: list[dict[str, Any]] = []
    for index, check in enumerate(validated):
        try:
            kind = str(check["type"])
            if kind == "required_state":
                passed, detail = _required_state(workspace, check)
            elif kind == "forbidden_state":
                passed, detail = _forbidden_state(workspace, check)
            elif kind in {"preserved_state", "decoy_untouched"}:
                passed, detail = _preserved_state(workspace, check, baseline.get(index))
            elif kind == "required_evidence":
                passed, detail = _required_evidence(events, check)
            else:  # validate_behavioral_checks makes this unreachable.
                raise BehavioralOracleError(f"unsupported behavioral check type: {kind}")
        except Exception as exc:
            passed = False
            detail = f"{type(exc).__name__}: {exc}"
        results.append({
            "index": index,
            "type": check["type"],
            "passed": passed,
            "detail": detail,
        })

    return {
        "schema": BEHAVIORAL_ORACLE_SCHEMA,
        "passed": all(result["passed"] for result in results),
        "checks_passed": sum(bool(result["passed"]) for result in results),
        "checks_total": len(results),
        "results": results,
        "affects_score": False,
    }
