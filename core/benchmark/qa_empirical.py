from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

from .raw import load_attempts


EMPIRICAL_QA_SCHEMA = "aios-bench/qa-empirical-evidence/v1"
EMPIRICAL_QA_PLAN_SCHEMA = "aios-bench/qa-empirical-plan/v1"
COLLECTION_AXES = (
    "current_revision_attempt",
    "second_profile",
    "second_harness",
    "second_model",
    "second_pressure_variant",
)


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


def _collection_state(*, attempts: int, profiles: int, harnesses: int, models: int, variants: int) -> dict[str, bool]:
    return {
        "current_revision_attempt": attempts >= 1,
        "second_profile": profiles >= 2,
        "second_harness": harnesses >= 2,
        "second_model": models >= 2,
        "second_pressure_variant": variants >= 2,
    }


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

    collection_state = _collection_state(
        attempts=len(eligible),
        profiles=len(profiles),
        harnesses=len(harnesses),
        models=len(models),
        variants=len(variants),
    )
    collection_gaps = [axis for axis in COLLECTION_AXES if not collection_state[axis]]

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
        "collection_state": collection_state,
        "collection_gaps": collection_gaps,
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
    gap_counts = {
        axis: sum(axis in row["collection_gaps"] for row in rows)
        for axis in COLLECTION_AXES
    }
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
        "collection_gap_counts": gap_counts,
        "tasks": rows,
    }


def build_empirical_qa_plan(raw_root: Path, tasks: Iterable[object]) -> dict[str, Any]:
    """Return missing evidence axes without deciding whether a task is saturated.

    Each axis is a minimum diversity observation, not a promotion threshold.
    Saturation remains a human QA conclusion informed by the observed outcome
    distribution once enough contrasting evidence has actually been collected.
    """
    evidence = build_empirical_qa_evidence(raw_root, tasks)
    planned_tasks = []
    for row in evidence["tasks"]:
        gaps = list(row["collection_gaps"])
        planned_tasks.append({
            "task_id": row["task_id"],
            "task_revision": row["task_revision"],
            "eligible_attempts": row["eligible_attempts"],
            "outcome_distribution": row["outcome_distribution"],
            "collection_gaps": gaps,
            "next_collection_targets": gaps,
            "additional_collection_needed": bool(gaps),
        })
    return {
        "schema": EMPIRICAL_QA_PLAN_SCHEMA,
        "raw_root": raw_root.as_posix(),
        "task_count": evidence["task_count"],
        "tasks_needing_additional_collection": sum(
            row["additional_collection_needed"] for row in planned_tasks
        ),
        "collection_gap_counts": dict(evidence["collection_gap_counts"]),
        "tasks": planned_tasks,
        "interpretation": (
            "Collection axes identify missing contrasting evidence only; they do not "
            "automatically pass multi-agent or saturation review."
        ),
    }


__all__ = [
    "COLLECTION_AXES",
    "EMPIRICAL_QA_PLAN_SCHEMA",
    "EMPIRICAL_QA_SCHEMA",
    "build_empirical_qa_evidence",
    "build_empirical_qa_plan",
]
