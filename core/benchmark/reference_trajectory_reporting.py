from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any, Iterable


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mean(items: list[dict[str, Any]], field: str) -> float | None:
    values = [_number(item.get(field)) for item in items]
    clean = [value for value in values if value is not None]
    return statistics.fmean(clean) if clean else None


def reference_trajectory_groups(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("status") == "unsupported" or row.get("comparable") is False:
            continue
        if suite is not None and str(row.get("suite")) != suite:
            continue
        if suite_revision is not None and str(row.get("suite_revision")) != suite_revision:
            continue
        reference = row.get("reference_trajectory")
        if not isinstance(reference, dict) or not reference.get("available"):
            continue
        key = (
            str(row.get("harness", row.get("agent", "unknown"))),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
            str(row.get("execution_fingerprint", "unreported")),
        )
        grouped[key].append(reference)

    result: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        complete = sum(bool(item.get("complete")) for item in items)
        result.append({
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "execution_fingerprint": key[4],
            "tasks_with_reference_trajectory": len(items),
            "complete_reference_trajectories": complete,
            "reference_trajectory_completion_rate": complete / len(items) if items else 0.0,
            "mean_milestone_completion": _mean(items, "milestone_completion"),
            "mean_events_to_completion": _mean(items, "events_to_completion"),
            "mean_reference_events_to_completion": _mean(items, "reference_events_to_completion"),
            "mean_effort_multiple_of_reference": _mean(items, "effort_multiple_of_reference"),
            "mean_post_completion_events": _mean(items, "post_completion_events"),
            "scope": "successful_reliable_canonical_events",
            "affects_score": False,
        })
    return result


__all__ = ["reference_trajectory_groups"]
