from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import defaultdict
from typing import Any, Iterable

from .statistics import wilson_interval


LANDSCAPE_SCHEMA = "aios-bench/pressure-landscape/v1"
PAIR_SCHEMA = "aios-bench/pressure-pair/v1"


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


def _params(row: dict[str, Any]) -> dict[str, Any] | None:
    value = row.get("variant_parameters")
    if not isinstance(value, dict) or not value:
        return None
    normalized: dict[str, Any] = {}
    for key, raw in sorted(value.items(), key=lambda item: str(item[0])):
        if isinstance(raw, bool):
            normalized[str(key)] = raw
        elif isinstance(raw, int):
            normalized[str(key)] = raw
        elif isinstance(raw, float) and math.isfinite(raw):
            normalized[str(key)] = raw
        elif isinstance(raw, str):
            normalized[str(key)] = raw
        else:
            normalized[str(key)] = str(raw)
    return normalized


def _vector_key(parameters: dict[str, Any]) -> str:
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sort_value(value: Any) -> tuple[int, Any]:
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, float(value))
    return (1, str(value))


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [
        row for row in rows
        if row.get("status") != "unsupported" and row.get("comparable") is not False
    ]
    scores = [score for row in comparable if (score := _number(row.get("score"))) is not None]
    successes = sum(bool(row.get("success")) for row in comparable)
    attempts = len(comparable)
    interval = wilson_interval(successes, attempts)
    failure_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        failure_counts[str(row.get("failure_kind") or "UNCLASSIFIED")] += 1
    variants = {
        str(row.get("variant_digest"))
        for row in rows
        if row.get("variant_digest")
    }
    seeds: set[int] = set()
    for row in rows:
        try:
            seeds.add(int(row["variant_seed"]))
        except (KeyError, TypeError, ValueError):
            pass
    return {
        "observations": len(rows),
        "comparable_observations": attempts,
        "scored_observations": len(scores),
        "successes": successes,
        "pass_rate": successes / attempts if attempts else None,
        "wilson_95": [interval[0], interval[1]] if attempts else [None, None],
        "mean_score": sum(scores) / len(scores) if scores else None,
        "median_score": statistics.median(scores) if scores else None,
        "score_range": [min(scores), max(scores)] if scores else None,
        "unique_variants": len(variants),
        "variant_seeds": sorted(seeds),
        "failure_counts": dict(sorted(failure_counts.items())),
    }


def pressure_landscapes(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate seeded parametric observations without assuming axis monotonicity.

    Full-vector cells preserve the joint pressure coordinates. Axis cells are
    explicitly marginal summaries over all observed values of the other
    coordinates; they are descriptive responses, not fitted difficulty curves.
    Strict model identity is part of the grouping key so different inference
    identities are never silently mixed into one landscape.
    """
    grouped: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not _matches_suite(row, suite, suite_revision):
            continue
        parameters = _params(row)
        family = row.get("variant_family")
        if parameters is None or not family:
            continue
        fingerprint = str(row.get("model_identity_fingerprint") or "unverified")
        key = (
            str(row.get("harness", row.get("agent", "unknown"))),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
            str(family),
            fingerprint,
        )
        grouped[key].append(row)

    output: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        vector_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        vector_params: dict[str, dict[str, Any]] = {}
        axis_groups: dict[str, dict[Any, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        execution_fingerprints: set[str] = set()
        all_strict = True
        for row in items:
            parameters = _params(row)
            if parameters is None:
                continue
            vector = _vector_key(parameters)
            vector_groups[vector].append(row)
            vector_params[vector] = parameters
            for axis, value in parameters.items():
                axis_groups[axis][value].append(row)
            if row.get("execution_fingerprint"):
                execution_fingerprints.add(str(row["execution_fingerprint"]))
            all_strict = all_strict and bool(row.get("model_strictly_comparable"))

        cells = [
            {
                "parameters": vector_params[vector],
                **_metrics(observations),
            }
            for vector, observations in sorted(vector_groups.items())
        ]
        axes: dict[str, list[dict[str, Any]]] = {}
        for axis, values in sorted(axis_groups.items()):
            axes[axis] = [
                {
                    "value": value,
                    "aggregation": "marginal_over_other_coordinates",
                    **_metrics(values[value]),
                }
                for value in sorted(values, key=_sort_value)
            ]

        output.append({
            "schema": LANDSCAPE_SCHEMA,
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "variant_family": key[4],
            "model_identity_fingerprint": None if key[5] == "unverified" else key[5],
            "strict_model_comparable": key[5] != "unverified" and all_strict,
            "execution_fingerprints": sorted(execution_fingerprints),
            "pressure_axes": sorted(axes),
            "observations": len(items),
            "full_vector_cells": cells,
            "axes": axes,
        })
    return output


def _pair_rejection(a_rows: list[dict[str, Any]], b_rows: list[dict[str, Any]]) -> str | None:
    a_fp = {str(row.get("model_identity_fingerprint")) for row in a_rows if row.get("model_identity_fingerprint")}
    b_fp = {str(row.get("model_identity_fingerprint")) for row in b_rows if row.get("model_identity_fingerprint")}
    if len(a_fp) != 1 or len(b_fp) != 1:
        return "model_identity_unverified"
    if a_fp != b_fp:
        return "model_identity_mismatch"
    if not all(bool(row.get("model_strictly_comparable")) for row in [*a_rows, *b_rows]):
        return "strict_model_comparability_missing"
    return None


def _stable_id(parameters: dict[str, Any]) -> str:
    payload = _vector_key(parameters).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def pressure_paired_comparisons(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Compare harnesses inside identical Frontier v4 pressure vectors.

    Matching requires experiment, repeat, task, task seed and variant digest.
    No observation is paired across independently generated variants or model
    identities. The output is descriptive; global paired inference remains in
    statistics.paired_comparisons().
    """
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not _matches_suite(row, suite, suite_revision):
            continue
        if row.get("schedule_mode") != "matched_interleaved" or not row.get("experiment_id"):
            continue
        if not row.get("variant_family") or _params(row) is None:
            continue
        key = (
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
            str(row.get("variant_family")),
        )
        groups[key].append(row)

    output: list[dict[str, Any]] = []
    for group_key, items in sorted(groups.items()):
        vector_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        vector_params: dict[str, dict[str, Any]] = {}
        for row in items:
            parameters = _params(row)
            if parameters is None:
                continue
            vector = _vector_key(parameters)
            vector_groups[vector].append(row)
            vector_params[vector] = parameters

        for vector, vector_rows in sorted(vector_groups.items()):
            by_harness: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in vector_rows:
                by_harness[str(row.get("harness", row.get("agent", "unknown")))].append(row)
            names = sorted(by_harness)
            for index_a in range(len(names)):
                for index_b in range(index_a + 1, len(names)):
                    harness_a, harness_b = names[index_a], names[index_b]
                    a_rows, b_rows = by_harness[harness_a], by_harness[harness_b]
                    base = {
                        "schema": PAIR_SCHEMA,
                        "model": group_key[0],
                        "suite": group_key[1],
                        "suite_revision": group_key[2],
                        "variant_family": group_key[3],
                        "pressure_cell_id": _stable_id(vector_params[vector]),
                        "parameters": vector_params[vector],
                        "harness_a": harness_a,
                        "harness_b": harness_b,
                    }
                    rejection = _pair_rejection(a_rows, b_rows)
                    if rejection is not None:
                        output.append({**base, "comparable": False, "reason": rejection, "matched_observations": 0})
                        continue

                    def indexed(source: list[dict[str, Any]]) -> dict[tuple[str, int, str, int, str], dict[str, Any]]:
                        result: dict[tuple[str, int, str, int, str], dict[str, Any]] = {}
                        for row in source:
                            if row.get("status") == "unsupported" or row.get("comparable") is False:
                                continue
                            if _number(row.get("score")) is None or not row.get("variant_digest"):
                                continue
                            try:
                                match = (
                                    str(row["experiment_id"]),
                                    int(row["repeat"]),
                                    str(row["task_id"]),
                                    int(row["task_seed"]),
                                    str(row["variant_digest"]),
                                )
                            except (KeyError, TypeError, ValueError):
                                continue
                            result[match] = row
                        return result

                    a_index = indexed(a_rows)
                    b_index = indexed(b_rows)
                    matched = sorted(set(a_index) & set(b_index))
                    deltas: list[float] = []
                    wins_a = wins_b = ties = 0
                    a_only = b_only = 0
                    for match in matched:
                        a = a_index[match]
                        b = b_index[match]
                        delta = float(a["score"]) - float(b["score"])
                        deltas.append(delta)
                        if delta > 0:
                            wins_a += 1
                        elif delta < 0:
                            wins_b += 1
                        else:
                            ties += 1
                        if bool(a.get("success")) and not bool(b.get("success")):
                            a_only += 1
                        if bool(b.get("success")) and not bool(a.get("success")):
                            b_only += 1
                    output.append({
                        **base,
                        "comparable": True,
                        "model_identity_fingerprint": next(
                            str(row["model_identity_fingerprint"])
                            for row in a_rows if row.get("model_identity_fingerprint")
                        ),
                        "matched_observations": len(matched),
                        "mean_score_delta_a_minus_b": sum(deltas) / len(deltas) if deltas else None,
                        "median_score_delta_a_minus_b": statistics.median(deltas) if deltas else None,
                        "wins_a": wins_a,
                        "wins_b": wins_b,
                        "ties": ties,
                        "a_pass_b_fail": a_only,
                        "b_pass_a_fail": b_only,
                    })
    return output
