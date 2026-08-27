from __future__ import annotations

import pytest

from core.benchmark.reference_trajectory import (
    ReferenceTrajectoryError,
    evaluate_reference_trajectory,
    validate_reference_trajectory,
)


REFERENCE = validate_reference_trajectory({
    "required_event_types": ["file_read", "file_write", "tool_call"],
    "milestones": [
        {"id": "inspect", "event_types": ["file_read"]},
        {"id": "modify", "event_types": ["file_write"]},
        {"id": "verify", "event_types": ["tool_call"]},
    ],
})


def _event(kind: str, sequence: int, **data):
    return {"type": kind, "source": "agent", "sequence": sequence, "data": data}


def test_reference_trajectory_matches_ordered_semantic_milestones() -> None:
    result = evaluate_reference_trajectory(
        REFERENCE,
        [
            _event("file_read", 1),
            _event("tool_call", 2),
            _event("file_write", 3),
            _event("tool_call", 4),
            _event("tool_call", 5),
        ],
        capability_success=True,
    )

    assert result["available"] is True
    assert result["complete"] is True
    assert result["events_to_completion"] == 4
    assert result["post_completion_events"] == 1
    assert result["calibrated_reference_effort_available"] is False
    assert [item["id"] for item in result["milestones"]] == ["inspect", "modify", "verify"]
    assert result["affects_score"] is False


def test_reference_trajectory_ignores_inferred_and_runner_owned_events() -> None:
    result = evaluate_reference_trajectory(
        REFERENCE,
        [
            _event("file_read", 1, inferred=True),
            {"type": "file_read", "source": "runner", "sequence": 2, "data": {}},
            _event("file_write", 3),
            _event("tool_call", 4),
        ],
        capability_success=True,
    )

    assert result["available"] is False
    assert result["reason"] == "required_telemetry_missing"
    assert result["missing_event_types"] == ["file_read"]


def test_reference_trajectory_is_not_compared_for_failed_capability() -> None:
    result = evaluate_reference_trajectory(REFERENCE, [], capability_success=False)

    assert result == {
        "available": False,
        "reason": "capability_not_successful",
        "affects_score": False,
    }


def test_reference_trajectory_can_be_available_but_incomplete() -> None:
    result = evaluate_reference_trajectory(
        REFERENCE,
        [
            _event("tool_call", 1),
            _event("file_write", 2),
            _event("file_read", 3),
        ],
        capability_success=True,
    )

    assert result["available"] is True
    assert result["complete"] is False
    assert result["matched_milestones"] == 1
    assert result["milestone_completion"] == 1 / 3
    assert result["events_to_completion"] is None


def test_reference_trajectory_validation_rejects_duplicate_milestones() -> None:
    with pytest.raises(ReferenceTrajectoryError, match="unique"):
        validate_reference_trajectory({
            "milestones": [
                {"id": "same", "event_types": ["file_read"]},
                {"id": "same", "event_types": ["file_write"]},
            ],
        })
