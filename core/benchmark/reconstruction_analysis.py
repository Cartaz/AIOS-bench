from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable


RECONSTRUCTION_ANALYSIS_SCHEMA = "aios-bench/reconstruction-analysis/v1"
_RATE_FIELDS = (
    "property_accuracy",
    "transfer_accuracy",
    "exact_case_accuracy",
    "output_field_accuracy",
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
    metrics = by_family.get("black_box_reconstruction")
    return metrics if isinstance(metrics, dict) else None


def black_box_reconstruction_metrics(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate hidden property/generalization verification diagnostics."""
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if suite is not None and str(row.get("suite")) != suite:
            continue
        if suite_revision is not None and str(row.get("suite_revision")) != suite_revision:
            continue
        if row.get("variant_family") != "black_box_reconstruction":
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
        means: dict[str, float | None] = {}
        for field in _RATE_FIELDS:
            values = [value for item in items if (value := _number(item.get(field))) is not None]
            means[f"mean_{field}"] = sum(values) / len(values) if values else None
        strict = sum(
            item.get("property_accuracy") == 1.0
            and item.get("transfer_accuracy") == 1.0
            and item.get("protocol_error_count") == 0
            and item.get("implementation_returncode") == 0
            and item.get("verifier_sandboxed") is True
            for item in items
        )
        probe_counts = [int(item.get("probe_count", 0)) for item in items]
        probe_budgets = [int(item.get("probe_budget", 0)) for item in items]
        output.append({
            "schema": RECONSTRUCTION_ANALYSIS_SCHEMA,
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "variant_family": "black_box_reconstruction",
            "observations": len(items),
            "strict_passes": strict,
            "strict_pass_rate": strict / len(items),
            "total_probes": sum(probe_counts),
            "total_probe_budget": sum(probe_budgets),
            "probe_utilization": (
                sum(probe_counts) / sum(probe_budgets)
                if sum(probe_budgets) > 0
                else None
            ),
            "total_protocol_errors": sum(int(item.get("protocol_error_count", 0)) for item in items),
            **means,
        })
    return output


__all__ = ["RECONSTRUCTION_ANALYSIS_SCHEMA", "black_box_reconstruction_metrics"]
