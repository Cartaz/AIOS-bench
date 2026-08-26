from __future__ import annotations

import hashlib
import itertools
import math
import random
import statistics as _statistics
from collections import defaultdict
from typing import Any, Iterable

from .resource_reporting import resource_efficiency_groups


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _stable_seed(*parts: object) -> int:
    payload = "\x1f".join(str(part) for part in parts)
    return int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest()[:8], "big")


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _matches_suite(row: dict[str, Any], suite: str | None, suite_revision: str | None) -> bool:
    if suite is not None and str(row.get("suite")) != suite:
        return False
    if suite_revision is not None and str(row.get("suite_revision")) != suite_revision:
        return False
    return True


def wilson_interval(successes: int, attempts: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a Bernoulli success proportion."""
    if attempts <= 0:
        return (0.0, 0.0)
    p = successes / attempts
    denominator = 1 + z * z / attempts
    centre = (p + z * z / (2 * attempts)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * attempts)) / attempts) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def aggregate_repeat_rows(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate repeated raw observations without replacing them."""
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("repeat") is None:
            continue
        if row.get("status") == "unsupported" or row.get("comparable") is False:
            continue
        if not _matches_suite(row, suite, suite_revision):
            continue
        key = (
            str(row.get("harness", row.get("agent", "unknown"))),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
            str(row.get("execution_fingerprint", "unreported")),
        )
        grouped[key].append(row)

    result: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            by_task[str(item.get("task_id", "unknown"))].append(item)
        task_stats: dict[str, Any] = {}
        all_scores: list[float] = []
        successes = 0
        attempts = 0
        repeats: set[int] = set()
        seeds: set[int] = set()
        for task_id, observations in sorted(by_task.items()):
            task_successes = sum(bool(item.get("success")) for item in observations)
            task_attempts = len(observations)
            scores = [score for item in observations if (score := _number(item.get("score"))) is not None]
            interval = wilson_interval(task_successes, task_attempts)
            task_stats[task_id] = {
                "attempts": task_attempts,
                "successes": task_successes,
                "pass_rate": task_successes / task_attempts if task_attempts else 0.0,
                "pass_at_k": task_successes > 0,
                "pass_pow_k": task_attempts > 0 and task_successes == task_attempts,
                "wilson_95": [interval[0], interval[1]],
                "median_score": _statistics.median(scores) if scores else None,
                "score_range": [min(scores), max(scores)] if scores else None,
            }
            all_scores.extend(scores)
            successes += task_successes
            attempts += task_attempts
            for item in observations:
                try:
                    repeats.add(int(item["repeat"]))
                except (KeyError, TypeError, ValueError):
                    pass
                try:
                    seeds.add(int(item["orchestration_seed"]))
                except (KeyError, TypeError, ValueError):
                    pass
        interval = wilson_interval(successes, attempts)
        result.append({
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "execution_fingerprint": key[4],
            "repeat_count": len(repeats),
            "repeats": sorted(repeats),
            "orchestration_seeds": sorted(seeds),
            "attempts": attempts,
            "successes": successes,
            "attempt_success_rate": successes / attempts if attempts else 0.0,
            "attempt_wilson_95": [interval[0], interval[1]],
            "median_score": _statistics.median(all_scores) if all_scores else None,
            "score_range": [min(all_scores), max(all_scores)] if all_scores else None,
            "tasks": task_stats,
        })
    return result


def _cluster_bootstrap_interval(
    clustered: dict[str, list[float]],
    *,
    seed: int,
    iterations: int = 4000,
) -> list[float | None]:
    clusters = sorted(key for key, values in clustered.items() if values)
    if not clusters:
        return [None, None]
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(iterations):
        values: list[float] = []
        for _ in clusters:
            values.extend(clustered[rng.choice(clusters)])
        samples.append(sum(values) / len(values))
    return [_quantile(samples, 0.025), _quantile(samples, 0.975)]


def _sign_flip_p_value(deltas: list[float], *, seed: int, iterations: int = 10000) -> float | None:
    if not deltas:
        return None
    observed = abs(sum(deltas) / len(deltas))
    if observed == 0:
        return 1.0
    rng = random.Random(seed)
    extreme = 0
    for _ in range(iterations):
        candidate = abs(sum(delta if rng.getrandbits(1) else -delta for delta in deltas) / len(deltas))
        if candidate >= observed - 1e-12:
            extreme += 1
    return (extreme + 1) / (iterations + 1)


def _pair_rejection_reason(a_rows: list[dict[str, Any]], b_rows: list[dict[str, Any]]) -> str | None:
    a_fp = {str(row.get("model_identity_fingerprint")) for row in a_rows if row.get("model_identity_fingerprint")}
    b_fp = {str(row.get("model_identity_fingerprint")) for row in b_rows if row.get("model_identity_fingerprint")}
    if len(a_fp) != 1 or len(b_fp) != 1:
        return "model_identity_unverified"
    if a_fp != b_fp:
        return "model_identity_mismatch"
    if not all(bool(row.get("model_strictly_comparable")) for row in [*a_rows, *b_rows]):
        return "strict_model_comparability_missing"
    return None


def paired_comparisons(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Compute strict matched harness deltas from interleaved experiment blocks.

    Pairs are fail-closed: both harnesses must report the same strict model
    identity fingerprint. Unmatched/unsupported/blocked observations are not
    imputed. Cluster bootstrap resamples task IDs, preserving all repeats for a
    sampled task. The sign-flip permutation test is deterministic Monte Carlo.
    """
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("schedule_mode") != "matched_interleaved" or not row.get("experiment_id"):
            continue
        if not _matches_suite(row, suite, suite_revision):
            continue
        key = (
            str(row.get("experiment_id")),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
        )
        grouped[key].append(row)

    comparisons: list[dict[str, Any]] = []
    for group_key, items in sorted(grouped.items()):
        by_harness: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in items:
            by_harness[str(row.get("harness", row.get("agent", "unknown")))].append(row)
        for harness_a, harness_b in itertools.combinations(sorted(by_harness), 2):
            a_rows = by_harness[harness_a]
            b_rows = by_harness[harness_b]
            base = {
                "experiment_id": group_key[0],
                "model": group_key[1],
                "suite": group_key[2],
                "suite_revision": group_key[3],
                "harness_a": harness_a,
                "harness_b": harness_b,
            }
            rejection = _pair_rejection_reason(a_rows, b_rows)
            if rejection is not None:
                comparisons.append({**base, "comparable": False, "reason": rejection, "matched_observations": 0})
                continue

            def index(rows_for_harness: list[dict[str, Any]]) -> dict[tuple[int, str, int], dict[str, Any]]:
                indexed: dict[tuple[int, str, int], dict[str, Any]] = {}
                for row in rows_for_harness:
                    if row.get("status") == "unsupported" or row.get("comparable") is False:
                        continue
                    if _number(row.get("score")) is None:
                        continue
                    try:
                        key = (int(row["repeat"]), str(row["task_id"]), int(row["task_seed"]))
                    except (KeyError, TypeError, ValueError):
                        continue
                    indexed[key] = row
                return indexed

            a_index = index(a_rows)
            b_index = index(b_rows)
            matched = sorted(set(a_index) & set(b_index))
            deltas: list[float] = []
            clustered: dict[str, list[float]] = defaultdict(list)
            wins_a = wins_b = ties = 0
            a_pass_b_fail = b_pass_a_fail = 0
            repeats: set[int] = set()
            for key in matched:
                a = a_index[key]
                b = b_index[key]
                delta = float(a["score"]) - float(b["score"])
                deltas.append(delta)
                clustered[key[1]].append(delta)
                repeats.add(key[0])
                if delta > 0:
                    wins_a += 1
                elif delta < 0:
                    wins_b += 1
                else:
                    ties += 1
                if bool(a.get("success")) and not bool(b.get("success")):
                    a_pass_b_fail += 1
                if bool(b.get("success")) and not bool(a.get("success")):
                    b_pass_a_fail += 1

            seed = _stable_seed(*group_key, harness_a, harness_b)
            comparisons.append({
                **base,
                "comparable": True,
                "model_identity_fingerprint": next(
                    str(row["model_identity_fingerprint"]) for row in a_rows if row.get("model_identity_fingerprint")
                ),
                "matched_observations": len(deltas),
                "matched_tasks": len(clustered),
                "repeats": sorted(repeats),
                "mean_score_delta_a_minus_b": sum(deltas) / len(deltas) if deltas else None,
                "median_score_delta_a_minus_b": _statistics.median(deltas) if deltas else None,
                "cluster_bootstrap_95": _cluster_bootstrap_interval(clustered, seed=seed),
                "sign_flip_p_value": _sign_flip_p_value(deltas, seed=seed ^ 0x5A17),
                "wins_a": wins_a,
                "wins_b": wins_b,
                "ties": ties,
                "a_pass_b_fail": a_pass_b_fail,
                "b_pass_a_fail": b_pass_a_fail,
            })
    return comparisons


def failure_distributions(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Count mutually exclusive failure kinds by harness/model execution profile."""
    groups: dict[tuple[str, str, str, str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: dict[tuple[str, str, str, str, str], int] = defaultdict(int)
    for row in rows:
        if not _matches_suite(row, suite, suite_revision):
            continue
        key = (
            str(row.get("harness", row.get("agent", "unknown"))),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
            str(row.get("execution_fingerprint", "unreported")),
        )
        kind = str(row.get("failure_kind") or "UNCLASSIFIED")
        groups[key][kind] += 1
        totals[key] += 1
    return [
        {
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "execution_fingerprint": key[4],
            "observations": totals[key],
            "counts": dict(sorted(groups[key].items())),
        }
        for key in sorted(groups)
    ]


def server_efficiency_groups(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate only server-verified usage for cross-harness efficiency."""
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not _matches_suite(row, suite, suite_revision):
            continue
        usage = row.get("server_usage")
        if not isinstance(usage, dict) or not usage.get("trusted_for_efficiency"):
            continue
        if row.get("usage_source") != "server_verified":
            continue
        key = (
            str(row.get("harness", row.get("agent", "unknown"))),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
            str(row.get("execution_fingerprint", "unreported")),
        )
        grouped[key].append(row)

    result: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        prompt_tokens = sum(_number((item.get("server_usage") or {}).get("prompt_tokens")) or 0.0 for item in items)
        output_tokens = sum(_number((item.get("server_usage") or {}).get("output_tokens")) or 0.0 for item in items)
        prompt_seconds = sum(_number((item.get("server_usage") or {}).get("prompt_seconds")) or 0.0 for item in items)
        generation_seconds = sum(_number((item.get("server_usage") or {}).get("generation_seconds")) or 0.0 for item in items)
        result.append({
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "execution_fingerprint": key[4],
            "server_verified_tasks": len(items),
            "prompt_tokens": int(round(prompt_tokens)),
            "output_tokens": int(round(output_tokens)),
            "prompt_seconds": prompt_seconds,
            "generation_seconds": generation_seconds,
            "prompt_tokens_per_second": prompt_tokens / prompt_seconds if prompt_seconds > 0 else None,
            "generation_tokens_per_second": output_tokens / generation_seconds if generation_seconds > 0 else None,
            "usage_source": "server_verified",
            "scope": "endpoint_aggregate",
            "requires_exclusive_server": True,
        })
    return result


def augment_summary_file(summary_path: Any, results_root: Any) -> None:
    """Add derived reliability, paired, failure, token, and resource statistics."""
    import json
    from pathlib import Path
    from .report import load_results

    path = Path(summary_path)
    summary = json.loads(path.read_text(encoding="utf-8"))
    rows = load_results(Path(results_root))
    filters = {
        "suite": summary.get("selected_suite"),
        "suite_revision": summary.get("selected_suite_revision"),
    }
    summary["repeat_groups"] = aggregate_repeat_rows(rows, **filters)
    summary["paired_comparisons"] = paired_comparisons(rows, **filters)
    summary["failure_distributions"] = failure_distributions(rows, **filters)
    summary["server_efficiency"] = server_efficiency_groups(rows, **filters)
    summary["resource_efficiency"] = resource_efficiency_groups(rows, **filters)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
