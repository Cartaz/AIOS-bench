from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

from .raw import load_attempts


EMPIRICAL_QA_SCHEMA = "aios-bench/qa-empirical-evidence/v1"


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _profile(row: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("harness", row.get("agent", "unknown"))),
        str(row.get("model", "unknown")),
    )


def _variant_signature(row: Mapping[str, Any]) -> str | None:
    parameters = row.get("variant_parameters")
    if not isinstance(parameters, Mapping):
        return None
    return json.dumps(dict(parameters), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _eligible(row: Mapping[str, Any], task_id: str, revision: int) -> bool:
    if str(row.get("suite", "")) != "frontier_v4":
        return False
    if str(row.get("task_id", "")) != task_id:
        return False
    try:
        observed_revision = int(row.get("task_revision"))
    except (TypeError, ValueError):
        return False
    if observed_revision != revision:
        return False
    if row.get("status") in {"unsupported", "blocked"}:
        return False
    if row.get("comparable") is False:
        return False
    return True


def _summarize_task(task: object, rows: list[dict[str, Any]]) -> dict[str, Any]:
    task_id = str(getattr(task, "id"))
    revision = int(getattr(task, "revision"))
    eligible = [row for row in rows if _eligible(row, task_id, revision)]
    profiles = sorted({_profile(row) for row in eligible})
    harnesses = sorted({profile[0] for profile in profiles})
    models = sorted({profile[1] for profile in profiles})
    passes = sum(row.get("success") is True for row in eligible)
    failures = sum(row.get("success") is False for row in eligible)
    scored = [score for row in eligible if (score := _number(row.get("score"))) is not None]
    variants = sorted({
        signature
        for row in eligible
        if (signature := _variant_signature(row)) is not None
    })

    if not eligible:
        outcome_distribution = "none"
    elif passes and failures:
        outcome_distribution = "mixed"
    elif passes:
        outcome_distribution = "all_pass"
    elif failures:
        outcome_distribution = "all_fail"
    else:
        outcome_distribution = "unscored"

    return {
        "task_id": task_id,
        "task_revision": revision,
        "eligible_attempts": len(eligible),
        "distinct_profiles": len(profiles),
        "profiles": [
            {"harness": harness, "model": model}
            for harness, model in profiles
        ],
        "distinct_harnesses": len(harnesses),
        "harnesses": harnesses,
        "distinct_models": len(models),
        "models": models,
        "pass_count": passes,
        "fail_count": failures,
        "outcome_distribution": outcome_distribution,
        "success_rate": passes / (passes + failures) if passes + failures else None,
        "score_min": min(scored) if scored else None,
        "score_median": median(scored) if scored else None,
        "score_max": max(scored) if scored else None,
        "distinct_pressure_variants": len(variants),
        "cross_profile_evidence_available": len(profiles) >= 2,
        "cross_harness_evidence_available": len(harnesses) >= 2,
        "cross_model_evidence_available": len(models) >= 2,
        "both_success_and_failure_observed": bool(passes and failures),
    }


def build_empirical_qa_evidence(
    raw_root: Path,
    tasks: Iterable[object],
) -> dict[str, Any]:
    """Describe current-revision Frontier v4 pilot evidence without judging adequacy.

    This report intentionally avoids arbitrary promotion/saturation thresholds.
    It exposes the empirical coverage needed for a human QA decision while
    keeping task lifecycle state owned by the QA registry.
    """
    task_list = list(tasks)
    attempts = load_attempts(raw_root)
    rows = [_summarize_task(task, attempts) for task in task_list]
    return {
        "schema": EMPIRICAL_QA_SCHEMA,
        "raw_root": raw_root.as_posix(),
        "task_count": len(rows),
        "tasks_with_evidence": sum(row["eligible_attempts"] > 0 for row in rows),
        "tasks_with_cross_profile_evidence": sum(
            row["cross_profile_evidence_available"] for row in rows
        ),
        "tasks_with_cross_harness_evidence": sum(
            row["cross_harness_evidence_available"] for row in rows
        ),
        "tasks_with_cross_model_evidence": sum(
            row["cross_model_evidence_available"] for row in rows
        ),
        "tasks_with_mixed_outcomes": sum(
            row["both_success_and_failure_observed"] for row in rows
        ),
        "tasks": rows,
    }


__all__ = ["EMPIRICAL_QA_SCHEMA", "build_empirical_qa_evidence"]
