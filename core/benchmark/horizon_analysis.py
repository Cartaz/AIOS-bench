from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any, Iterable, Mapping

from .horizon import HORIZON_CONTEXT_KIND
from .statistics import wilson_interval


HORIZON_RESPONSE_SCHEMA = "aios-bench/long-horizon-response/v1"


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _context(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = row.get("experiment_context")
    if not isinstance(value, Mapping) or value.get("kind") != HORIZON_CONTEXT_KIND:
        return None
    return value


def _cell_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [
        row
        for row in rows
        if row.get("status") != "unsupported" and row.get("comparable") is not False
    ]
    successes = sum(bool(row.get("success")) for row in comparable)
    attempts = len(comparable)
    interval = wilson_interval(successes, attempts)
    scores = [value for row in comparable if (value := _number(row.get("score"))) is not None]
    durations = [
        value
        for row in comparable
        if (value := _number(row.get("duration_seconds"))) is not None
    ]
    inputs = [
        value for row in comparable if (value := _number(row.get("input_tokens"))) is not None
    ]
    outputs = [
        value for row in comparable if (value := _number(row.get("output_tokens"))) is not None
    ]
    failure_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        failure_counts[str(row.get("failure_kind") or "UNCLASSIFIED")] += 1
    variants = {
        str(row["variant_digest"])
        for row in rows
        if row.get("variant_digest")
    }
    return {
        "observations": len(rows),
        "comparable_observations": attempts,
        "unsupported_observations": sum(row.get("status") == "unsupported" for row in rows),
        "successes": successes,
        "pass_rate": successes / attempts if attempts else None,
        "wilson_95": [interval[0], interval[1]] if attempts else [None, None],
        "mean_score": sum(scores) / len(scores) if scores else None,
        "median_score": statistics.median(scores) if scores else None,
        "median_duration_seconds": statistics.median(durations) if durations else None,
        "mean_input_tokens": sum(inputs) / len(inputs) if inputs else None,
        "mean_output_tokens": sum(outputs) / len(outputs) if outputs else None,
        "unique_variants": len(variants),
        "failure_counts": dict(sorted(failure_counts.items())),
    }


def _canonical_parameters(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return {str(key): value[key] for key in sorted(value, key=str)}


def long_horizon_response_curves(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate deliberate generated pressure paths without assuming monotonic difficulty.

    The unit of interpretation remains the exact benchmark-owned pressure cell.
    Cell order is a controlled workload path only; marginal or ordinal position
    is never converted into an assumed difficulty score.
    """
    groups: dict[
        tuple[str, str, str, str, str, str, str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)
    for row in rows:
        if suite is not None and str(row.get("suite")) != suite:
            continue
        if suite_revision is not None and str(row.get("suite_revision")) != suite_revision:
            continue
        context = _context(row)
        if context is None:
            continue
        family = str(context.get("family", ""))
        profile_id = str(context.get("profile_id", ""))
        profile_digest = str(context.get("profile_digest", ""))
        if not family or not profile_id or not profile_digest:
            continue
        model_fingerprint = str(row.get("model_identity_fingerprint") or "unverified")
        landscape_profile = str(
            row.get("landscape_execution_fingerprint")
            or f"legacy:{row.get('execution_fingerprint', 'unreported')}"
        )
        key = (
            str(row.get("harness", row.get("agent", "unknown"))),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
            profile_id,
            profile_digest,
            family,
            f"{model_fingerprint}|{landscape_profile}",
        )
        groups[key].append(row)

    output: list[dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
        contexts: dict[str, Mapping[str, Any]] = {}
        expected_ids: set[str] = set()
        expected_count: int | None = None
        parameter_identity_consistent = True
        seed_control: dict[int, set[int]] = defaultdict(set)
        all_strict = True

        for row in items:
            context = _context(row)
            if context is None:
                continue
            cell_id = str(context.get("cell_id", ""))
            if not cell_id:
                continue
            by_cell[cell_id].append(row)
            contexts[cell_id] = context
            family_ids = context.get("family_cell_ids")
            if isinstance(family_ids, list):
                expected_ids.update(str(value) for value in family_ids)
            try:
                declared_count = int(context.get("family_cell_count"))
            except (TypeError, ValueError):
                declared_count = None
            if declared_count is not None:
                expected_count = declared_count if expected_count is None else expected_count
                if expected_count != declared_count:
                    parameter_identity_consistent = False
            context_parameters = _canonical_parameters(context.get("parameters"))
            row_parameters = _canonical_parameters(row.get("variant_parameters"))
            if context_parameters != row_parameters:
                parameter_identity_consistent = False
            try:
                repeat = int(row["repeat"])
                task_seed = int(row["task_seed"])
            except (KeyError, TypeError, ValueError):
                pass
            else:
                seed_control[repeat].add(task_seed)
            all_strict = all_strict and bool(row.get("model_strictly_comparable"))

        cells: list[dict[str, Any]] = []
        for cell_id, observations in by_cell.items():
            context = contexts[cell_id]
            try:
                cell_index = int(context.get("cell_index"))
            except (TypeError, ValueError):
                cell_index = 0
            try:
                path_index = int(context.get("path_index"))
            except (TypeError, ValueError):
                path_index = 0
            cells.append({
                "cell_id": cell_id,
                "cell_index": cell_index,
                "path_index": path_index,
                "task_id": str(context.get("task_id", "")),
                "parameters": _canonical_parameters(context.get("parameters")),
                "axis_roles": _canonical_parameters(context.get("axis_roles")),
                **_cell_metrics(observations),
            })
        cells.sort(key=lambda cell: (cell["path_index"], cell["cell_index"], cell["cell_id"]))

        observed_ids = set(by_cell)
        if not expected_ids:
            expected_ids = observed_ids
        if expected_count is None:
            expected_count = len(expected_ids)
        missing_ids = sorted(expected_ids - observed_ids)
        seed_control_consistent = bool(seed_control) and all(
            len(values) == 1 for values in seed_control.values()
        )
        model_fingerprint, landscape_profile = key[7].split("|", 1)
        output.append({
            "schema": HORIZON_RESPONSE_SCHEMA,
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "profile_id": key[4],
            "profile_digest": key[5],
            "variant_family": key[6],
            "model_identity_fingerprint": (
                None if model_fingerprint == "unverified" else model_fingerprint
            ),
            "landscape_execution_fingerprint": landscape_profile,
            "strict_model_comparable": (
                model_fingerprint != "unverified" and all_strict
            ),
            "interpretation": (
                "ordered generated workload path; descriptive capability response, "
                "not an assumed monotonic difficulty curve"
            ),
            "expected_cells": expected_count,
            "observed_cells": len(observed_ids),
            "complete_cell_coverage": not missing_ids and len(observed_ids) == expected_count,
            "missing_cell_ids": missing_ids,
            "parameter_identity_consistent": parameter_identity_consistent,
            "seed_control_consistent": seed_control_consistent,
            "response_curve": cells,
        })
    return output


__all__ = ["HORIZON_RESPONSE_SCHEMA", "long_horizon_response_curves"]
