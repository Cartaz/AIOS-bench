from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable


EPISTEMIC_ANALYSIS_SCHEMA = "aios-bench/epistemic-analysis/v1"
_RATE_FIELDS = (
    "full_decision_accuracy",
    "valid_twin_acceptance_rate",
    "corrupted_twin_rejection_rate",
    "false_premise_compliance_rate",
    "overcautious_refusal_rate",
    "premise_accuracy",
    "evidence_accuracy",
    "pair_action_accuracy",
)
_COUNT_FIELDS = (
    "pair_count",
    "case_count",
    "missing_case_count",
    "extra_case_count",
    "duplicate_case_count",
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
    metrics = by_family.get("epistemic_twins")
    return metrics if isinstance(metrics, dict) else None


def epistemic_twin_metrics(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate both sides of paired premise discrimination without an LLM judge."""
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if suite is not None and str(row.get("suite")) != suite:
            continue
        if suite_revision is not None and str(row.get("suite_revision")) != suite_revision:
            continue
        if row.get("variant_family") != "epistemic_twins":
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
            "schema": EPISTEMIC_ANALYSIS_SCHEMA,
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "variant_family": "epistemic_twins",
            "observations": len(items),
            "strict_passes": strict_passes,
            "strict_pass_rate": strict_passes / len(items),
            **rates,
            **counts,
        })
    return output


__all__ = ["EPISTEMIC_ANALYSIS_SCHEMA", "epistemic_twin_metrics"]
