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


def classify_failure(
    *,
    status: str,
    success: bool,
    execution_success: bool,
    evaluation_passed: bool | None,
    events: Iterable[dict[str, Any]] = (),
) -> str:
    """Map runner state to a stable, mutually exclusive failure category."""
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
    if has_structured_refusal(events):
        return REFUSED
    if execution_success and evaluation_passed is False:
        return WRONG
    return CRASH
