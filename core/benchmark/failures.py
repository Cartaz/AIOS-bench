from __future__ import annotations

from typing import Any, Iterable


PASS = "PASS"
WRONG = "WRONG"
CRASH = "CRASH"
TIMEOUT = "TIMEOUT"
RUNAWAY = "RUNAWAY"
REFUSED = "REFUSED"
INFRA_ERROR = "INFRA_ERROR"
UNSUPPORTED = "UNSUPPORTED"
BLOCKED = "BLOCKED"
TOOL_SELECTION_ERROR = "TOOL_SELECTION_ERROR"
TOOL_SCHEMA_ERROR = "TOOL_SCHEMA_ERROR"
RETRY_LOOP = "RETRY_LOOP"
RECOVERY_FAILURE = "RECOVERY_FAILURE"
INCOMPLETE_RETRIEVAL = "INCOMPLETE_RETRIEVAL"
WRONG_AUTHORITY = "WRONG_AUTHORITY"
CROSS_ARTIFACT_MISMATCH = "CROSS_ARTIFACT_MISMATCH"

DETERMINISTIC_EVALUATION_FAILURES = frozenset({
    TOOL_SELECTION_ERROR,
    TOOL_SCHEMA_ERROR,
    RETRY_LOOP,
    RECOVERY_FAILURE,
    INCOMPLETE_RETRIEVAL,
    WRONG_AUTHORITY,
    CROSS_ARTIFACT_MISMATCH,
})

FAILURE_KINDS = frozenset({
    PASS,
    WRONG,
    CRASH,
    TIMEOUT,
    RUNAWAY,
    REFUSED,
    INFRA_ERROR,
    UNSUPPORTED,
    BLOCKED,
    *DETERMINISTIC_EVALUATION_FAILURES,
})


def has_structured_refusal(events: Iterable[dict[str, Any]]) -> bool:
    """Return true only for explicit structured refusal telemetry."""
    for event in events:
        if event.get("type") == "refusal":
            return True
        if event.get("type") != "assistant_message":
            continue
        data = event.get("data") or {}
        stop_reason = str(data.get("stop_reason", "")).strip().lower()
        if stop_reason in {"refusal", "refused", "content_filter", "safety"}:
            return True
    return False


def _evaluation_failure_hint(events: Iterable[dict[str, Any]]) -> str | None:
    for event in events:
        if event.get("type") != "deterministic_evaluation":
            continue
        result = event.get("result")
        if not isinstance(result, dict):
            continue
        candidate = result.get("failure_kind")
        if candidate in DETERMINISTIC_EVALUATION_FAILURES:
            return str(candidate)
    return None


def classify_failure(
    *,
    status: str,
    success: bool,
    execution_success: bool,
    evaluation_passed: bool | None,
    events: Iterable[dict[str, Any]] = (),
    evaluation_failure_kind: str | None = None,
) -> str:
    """Map runner state to a stable, mutually exclusive failure category.

    Runtime/lifecycle failures take precedence over deterministic grader
    diagnoses. A family-specific hint is eligible only after the harness
    completed successfully and the deterministic evaluation failed.
    """
    event_list = list(events)
    normalized = str(status).strip().lower()
    if success:
        return PASS
    if normalized == "unsupported":
        return UNSUPPORTED
    if normalized == "blocked":
        return BLOCKED
    if normalized == "runaway":
        return RUNAWAY
    if normalized == "timeout":
        return TIMEOUT
    if normalized == "error":
        return INFRA_ERROR
    if has_structured_refusal(event_list):
        return REFUSED
    if execution_success and evaluation_passed is False:
        hint = evaluation_failure_kind or _evaluation_failure_hint(event_list)
        if hint in DETERMINISTIC_EVALUATION_FAILURES:
            return str(hint)
        return WRONG
    return CRASH
