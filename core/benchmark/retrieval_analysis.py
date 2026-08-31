from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable


RETRIEVAL_ANALYSIS_SCHEMA = "aios-bench/retrieval-analysis/v1"
_RATE_FIELDS = (
    "record_precision",
    "record_recall",
    "record_f1",
    "field_accuracy",
    "provenance_recall",
)
_COUNT_FIELDS = (
    "expected_records",
    "predicted_rows",
    "missing_record_count",
    "extra_record_count",
    "duplicate_prediction_count",
    "wrong_authority_count",
    "stale_source_count",
    "mirror_source_count",
)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _metrics(row: dict[str, Any]) -> dict[str, Any] | None:
    evaluation = row.get("evaluation")
    if not isinstance(evaluation, dict):
        return None
    by_family = evaluation.get("metrics")
    if not isinstance(by_family, dict):
        return None
    metrics = by_family.get("wide_retrieval")
    return metrics if isinstance(metrics, dict) else None


def wide_retrieval_metrics(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate deterministic Wide Retrieval metrics for canonical rows.

    Callers own intervention filtering; this function only enforces ordinary
    task comparability and the requested suite identity.
    """
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if suite is not None and str(row.get("suite")) != suite:
            continue
        if suite_revision is not None and str(row.get("suite_revision")) != suite_revision:
            continue
        if row.get("variant_family") != "wide_retrieval":
            continue
        if row.get("status") == "unsupported" or row.get("comparable") is False:
            continue
        metrics = _metrics(row)
        if metrics is None:
            continue
        key = (
            str(row.get("harness", row.get("agent", "unknown"))),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
        )
        groups[key].append(metrics)

    output: list[dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        rates: dict[str, float | None] = {}
        for field in _RATE_FIELDS:
            values = [value for item in items if (value := _number(item.get(field))) is not None]
            rates[f"mean_{field}"] = sum(values) / len(values) if values else None

        counts: dict[str, int] = {}
        for field in _COUNT_FIELDS:
            values = [value for item in items if (value := _number(item.get(field))) is not None]
            counts[f"total_{field}"] = int(sum(values)) if values else 0

        strict_passes = sum(item.get("strict_complete_pass") is True for item in items)
        output.append({
            "schema": RETRIEVAL_ANALYSIS_SCHEMA,
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "variant_family": "wide_retrieval",
            "observations": len(items),
            "strict_passes": strict_passes,
            "strict_pass_rate": strict_passes / len(items),
            **rates,
            **counts,
        })
    return output


__all__ = ["RETRIEVAL_ANALYSIS_SCHEMA", "wide_retrieval_metrics"]
