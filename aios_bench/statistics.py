from __future__ import annotations

import math
import statistics as _statistics
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
    """Aggregate only rows explicitly annotated as repeated observations.

    The Wilson interval is attempt-level and diagnostic. Publication-grade
    paired/cluster uncertainty is intentionally left to the next protocol phase.
    """
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("repeat") is None:
            continue
        if row.get("status") == "unsupported" or row.get("comparable") is False:
            continue
        if suite is not None and str(row.get("suite")) != suite:
            continue
        if suite_revision is not None and str(row.get("suite_revision")) != suite_revision:
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


def augment_summary_file(summary_path: Any, results_root: Any) -> None:
    """Add repeat statistics to a generated summary without changing raw results."""
    import json
    from pathlib import Path
    from .report import load_results

    path = Path(summary_path)
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["repeat_groups"] = aggregate_repeat_rows(
        load_results(Path(results_root)),
        suite=summary.get("selected_suite"),
        suite_revision=summary.get("selected_suite_revision"),
    )
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
