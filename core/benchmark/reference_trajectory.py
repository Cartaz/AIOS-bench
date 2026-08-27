from __future__ import annotations

from typing import Any, Mapping, Sequence


class ReferenceTrajectoryError(ValueError):
    pass


def validate_reference_trajectory(value: object) -> dict[str, Any] | None:
    if value in (None, {}):
        return None
    if not isinstance(value, Mapping):
        raise ReferenceTrajectoryError("trajectory_reference must be an object")
    required_raw = value.get("required_event_types", [])
    milestones_raw = value.get("milestones", [])
    reference_events = value.get("reference_events_to_completion")
    if not isinstance(required_raw, list) or not all(isinstance(item, str) and item for item in required_raw):
        raise ReferenceTrajectoryError("required_event_types must be non-empty strings")
    if not isinstance(milestones_raw, list) or not milestones_raw:
        raise ReferenceTrajectoryError("milestones must be a non-empty array")
    milestones: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in milestones_raw:
        if not isinstance(raw, Mapping):
            raise ReferenceTrajectoryError("milestone must be an object")
        milestone_id = str(raw.get("id", ""))
        event_types = raw.get("event_types", [])
        if not milestone_id or milestone_id in seen:
            raise ReferenceTrajectoryError("milestone ids must be unique and non-empty")
        if not isinstance(event_types, list) or not event_types or not all(isinstance(item, str) and item for item in event_types):
            raise ReferenceTrajectoryError(f"milestone {milestone_id} needs event_types")
        seen.add(milestone_id)
        milestones.append({"id": milestone_id, "event_types": tuple(event_types)})
    try:
        reference_count = int(reference_events)
    except (TypeError, ValueError) as exc:
        raise ReferenceTrajectoryError("reference_events_to_completion must be an integer") from exc
    if reference_count < len(milestones):
        raise ReferenceTrajectoryError("reference_events_to_completion cannot be smaller than milestone count")
    return {
        "required_event_types": tuple(required_raw),
        "milestones": tuple(milestones),
        "reference_events_to_completion": reference_count,
    }


def _reliable_events(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    reliable: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        data = event.get("data")
        if isinstance(data, Mapping) and data.get("inferred") is True:
            continue
        if str(event.get("source", "")) == "runner":
            continue
        reliable.append(dict(event))
    return reliable


def evaluate_reference_trajectory(
    reference: Mapping[str, Any] | None,
    events: Sequence[Mapping[str, Any]],
    *,
    capability_success: bool,
) -> dict[str, Any] | None:
    if reference is None:
        return None
    if not capability_success:
        return {
            "available": False,
            "reason": "capability_not_successful",
            "affects_score": False,
        }
    reliable = _reliable_events(events)
    observed_types = {str(event.get("type", "unknown")) for event in reliable}
    required_types = tuple(str(item) for item in reference.get("required_event_types", ()))
    missing_types = [kind for kind in required_types if kind not in observed_types]
    if missing_types:
        return {
            "available": False,
            "reason": "required_telemetry_missing",
            "missing_event_types": missing_types,
            "reliable_events": len(reliable),
            "affects_score": False,
        }

    milestones = list(reference.get("milestones", ()))
    cursor = 0
    matched: list[dict[str, Any]] = []
    for milestone in milestones:
        accepted = set(str(item) for item in milestone["event_types"])
        found = None
        for index in range(cursor, len(reliable)):
            if str(reliable[index].get("type", "unknown")) in accepted:
                found = index
                break
        if found is None:
            break
        event = reliable[found]
        matched.append({
            "id": str(milestone["id"]),
            "event_type": str(event.get("type", "unknown")),
            "sequence": event.get("sequence"),
            "reliable_event_index": found + 1,
        })
        cursor = found + 1

    total = len(milestones)
    complete = len(matched) == total
    events_to_completion = cursor if complete else None
    reference_events = int(reference["reference_events_to_completion"])
    return {
        "available": True,
        "complete": complete,
        "matched_milestones": len(matched),
        "total_milestones": total,
        "milestone_completion": len(matched) / total if total else 1.0,
        "milestones": matched,
        "reliable_events": len(reliable),
        "events_to_completion": events_to_completion,
        "reference_events_to_completion": reference_events,
        "effort_multiple_of_reference": (
            events_to_completion / reference_events if events_to_completion is not None else None
        ),
        "post_completion_events": (
            len(reliable) - events_to_completion if events_to_completion is not None else None
        ),
        "scope": "successful_reliable_canonical_events",
        "affects_score": False,
    }


__all__ = [
    "ReferenceTrajectoryError",
    "evaluate_reference_trajectory",
    "validate_reference_trajectory",
]
