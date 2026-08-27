from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any, Iterable


COVERAGE_SCHEMA = "aios-bench/coverage/v1"


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _matches_suite(row: dict[str, Any], suite: str | None, suite_revision: str | None) -> bool:
    if suite is not None and str(row.get("suite")) != suite:
        return False
    if suite_revision is not None and str(row.get("suite_revision")) != suite_revision:
        return False
    return True


def task_coverage_metrics(row: dict[str, Any]) -> dict[str, Any] | None:
    evaluation = row.get("evaluation")
    if not isinstance(evaluation, dict):
        return None
    results = evaluation.get("results")
    if not isinstance(results, list):
        return None
    for result in results:
        if not isinstance(result, dict):
            continue
        metrics = result.get("metrics")
        if isinstance(metrics, dict) and metrics.get("schema") == COVERAGE_SCHEMA:
            return dict(metrics)
    return None


def _mean(items: list[dict[str, Any]], field: str) -> float | None:
    values = [_number(item.get(field)) for item in items]
    clean = [value for value in values if value is not None]
    return statistics.fmean(clean) if clean else None


def coverage_completeness_groups(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate persisted deterministic coverage metrics by execution profile."""
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("status") == "unsupported" or row.get("comparable") is False:
            continue
        if not _matches_suite(row, suite, suite_revision):
            continue
        metrics = task_coverage_metrics(row)
        if metrics is None:
            continue
        key = (
            str(row.get("harness", row.get("agent", "unknown"))),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
            str(row.get("execution_fingerprint", "unreported")),
        )
        grouped[key].append(metrics)

    groups: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        groups.append({
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "execution_fingerprint": key[4],
            "tasks_with_coverage": len(items),
            "exact_completion_tasks": sum(
                item.get("false_positives") == 0 and item.get("false_negatives") == 0
                for item in items
            ),
            "mean_precision": _mean(items, "precision"),
            "mean_recall": _mean(items, "recall"),
            "mean_completion": _mean(items, "completion"),
            "total_true_positives": int(sum(int(item.get("true_positives", 0) or 0) for item in items)),
            "total_false_positives": int(sum(int(item.get("false_positives", 0) or 0) for item in items)),
            "total_false_negatives": int(sum(int(item.get("false_negatives", 0) or 0) for item in items)),
            "scope": "deterministic_task_owned_finite_sets",
            "affects_score": False,
        })
    return groups


__all__ = ["COVERAGE_SCHEMA", "coverage_completeness_groups", "task_coverage_metrics"]
