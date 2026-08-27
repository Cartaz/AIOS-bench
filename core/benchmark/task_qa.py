from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping


QA_SCHEMA = "aios-bench/task-qa/v2"
QA_REPORT_SCHEMA = "aios-bench/task-qa-report/v2"
QA_REVIEW_INTERVAL_DAYS = 180
LIFECYCLES = frozenset({"draft", "pilot", "stable", "retired"})
REVIEW_STATUSES = frozenset({"pending", "passed", "failed", "not_applicable"})
REVIEW_KEYS = (
    "ambiguity_oracle_review",
    "cheat_adversarial_review",
    "multi_agent_pilot",
    "contamination_review",
    "saturation_review",
)
EXPOSURE_LEVELS = frozenset({"private", "limited", "public_repository"})
_SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class TaskQAError(ValueError):
    pass


def task_semantic_payload(task: object) -> dict[str, Any]:
    """Return the task-owned fields whose changes invalidate a prior QA audit."""
    return {
        "id": str(getattr(task, "id")),
        "category": str(getattr(task, "category", "")),
        "prompt": str(getattr(task, "prompt", "")),
        "mode": str(getattr(task, "mode", "cold")),
        "tier": int(getattr(task, "tier", 3)),
        "revision": int(getattr(task, "revision", 1)),
        "tags": list(getattr(task, "tags", ())),
        "required_capabilities": list(getattr(task, "required_capabilities", ())),
        "depends_on": list(getattr(task, "depends_on", ())),
        "acceptance": list(getattr(task, "acceptance", ())),
        "behavioral_acceptance": list(getattr(task, "behavioral_acceptance", ())),
        "trajectory_reference": getattr(task, "trajectory_reference", None),
    }


def task_semantic_digest(task: object) -> str:
    payload = json.dumps(
        task_semantic_payload(task),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_task_qa(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TaskQAError(f"cannot load QA registry: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != QA_SCHEMA:
        raise TaskQAError(f"QA registry must use schema {QA_SCHEMA}")
    records = value.get("tasks")
    if not isinstance(records, list):
        raise TaskQAError("QA registry tasks must be an array")
    return [dict(item) if isinstance(item, Mapping) else item for item in records]


def _review_state(record: Mapping[str, Any]) -> tuple[bool, list[str], list[str]]:
    reviews = record.get("reviews")
    if not isinstance(reviews, Mapping):
        return False, ["reviews must be an object"], list(REVIEW_KEYS)
    errors: list[str] = []
    pending: list[str] = []
    unknown = sorted(set(str(key) for key in reviews) - set(REVIEW_KEYS))
    missing = [key for key in REVIEW_KEYS if key not in reviews]
    if unknown:
        errors.append(f"unknown review keys: {unknown}")
    if missing:
        errors.append(f"missing review keys: {missing}")
    for key in REVIEW_KEYS:
        raw = reviews.get(key)
        if not isinstance(raw, Mapping):
            if key not in missing:
                errors.append(f"{key} must be an object")
            continue
        status = str(raw.get("status", ""))
        evidence = raw.get("evidence")
        if status not in REVIEW_STATUSES:
            errors.append(f"{key} has invalid status {status!r}")
            continue
        if status in {"passed", "failed", "not_applicable"} and not (
            isinstance(evidence, str) and evidence.strip()
        ):
            errors.append(f"{key} status {status} requires evidence")
        if status == "pending":
            pending.append(key)
    ready = not errors and all(
        isinstance(reviews.get(key), Mapping)
        and str(reviews[key].get("status")) in {"passed", "not_applicable"}
        for key in REVIEW_KEYS
    )
    return ready, errors, pending


def validate_task_qa_records(
    tasks: Iterable[object],
    records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    task_map = {str(getattr(task, "id")): task for task in tasks}
    seen: set[str] = set()
    errors: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []

    for raw in records:
        if not isinstance(raw, Mapping):
            errors.append({"task_id": None, "error": "QA record must be an object"})
            continue
        task_id = str(raw.get("task_id", ""))
        record_errors: list[str] = []
        if not _SAFE_ID.fullmatch(task_id):
            record_errors.append("invalid task_id")
        if task_id in seen:
            record_errors.append("duplicate QA record")
        seen.add(task_id)
        task = task_map.get(task_id)
        if task is None:
            record_errors.append("QA record does not match a catalog task")
        try:
            revision = int(raw.get("task_revision"))
        except (TypeError, ValueError):
            revision = -1
            record_errors.append("task_revision must be an integer")
        if task is not None and revision != int(getattr(task, "revision")):
            record_errors.append(
                f"stale task_revision {revision}; catalog has {int(getattr(task, 'revision'))}"
            )

        semantic_digest = str(raw.get("task_semantic_digest", ""))
        if not _SHA256.fullmatch(semantic_digest):
            record_errors.append("task_semantic_digest must be a lowercase SHA-256 hex digest")
        elif task is not None:
            expected_digest = task_semantic_digest(task)
            if semantic_digest != expected_digest:
                record_errors.append(
                    f"stale task_semantic_digest {semantic_digest}; catalog has {expected_digest}"
                )

        lifecycle = str(raw.get("lifecycle", ""))
        if lifecycle not in LIFECYCLES:
            record_errors.append(f"invalid lifecycle {lifecycle!r}")
        exposure = str(raw.get("exposure", ""))
        if exposure not in EXPOSURE_LEVELS:
            record_errors.append(f"invalid exposure {exposure!r}")
        known_issues = raw.get("known_issues")
        if not isinstance(known_issues, list) or not all(
            isinstance(item, str) and item.strip() for item in known_issues
        ):
            record_errors.append("known_issues must be an array of non-empty strings")
            known_issues = []
        audited_at = raw.get("audited_at")
        if not isinstance(audited_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", audited_at):
            record_errors.append("audited_at must be YYYY-MM-DD")
        else:
            try:
                date.fromisoformat(audited_at)
            except ValueError:
                record_errors.append("audited_at must be a valid calendar date")
        manual_ready, review_errors, pending = _review_state(raw)
        record_errors.extend(review_errors)
        if lifecycle == "stable" and not manual_ready:
            record_errors.append("stable lifecycle requires all manual reviews passed/not_applicable")
        if lifecycle == "stable" and known_issues:
            record_errors.append("stable lifecycle requires no known issues")

        normalized_record = {
            "task_id": task_id,
            "task_revision": revision,
            "task_semantic_digest": semantic_digest,
            "lifecycle": lifecycle,
            "exposure": exposure,
            "known_issues": list(known_issues),
            "audited_at": audited_at,
            "manual_reviews_ready": manual_ready,
            "pending_reviews": pending,
        }
        normalized.append(normalized_record)
        for error in record_errors:
            errors.append({"task_id": task_id or None, "error": error})

    for task_id in sorted(set(task_map) - seen):
        errors.append({"task_id": task_id, "error": "missing QA record"})

    return {
        "schema": QA_SCHEMA,
        "registry_ok": not errors,
        "task_count": len(task_map),
        "record_count": len(normalized),
        "records": normalized,
        "errors": errors,
    }


def _automated_by_task(validation: Mapping[str, Any]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    observations = validation.get("observations")
    if not isinstance(observations, list):
        return result
    for item in observations:
        if not isinstance(item, Mapping) or not item.get("task_id"):
            continue
        task_id = str(item["task_id"])
        if "same_seed_deterministic" in item:
            result[task_id] = all(
                bool(item.get(field))
                for field in (
                    "same_seed_deterministic",
                    "different_seed_changes_variant",
                    "untouched_variant_fails",
                    "golden_variant_passes",
                )
            )
        else:
            result[task_id] = bool(
                item.get("untouched_fixture_fails") and item.get("golden_solution_passes")
            )
    return result


def _audit_age(record: Mapping[str, Any], as_of: date) -> dict[str, Any]:
    try:
        audited = date.fromisoformat(str(record.get("audited_at", "")))
    except ValueError:
        return {
            "audit_age_days": None,
            "next_review_due_at": None,
            "maintenance_due": True,
        }
    due = audited + timedelta(days=QA_REVIEW_INTERVAL_DAYS)
    return {
        "audit_age_days": (as_of - audited).days,
        "next_review_due_at": due.isoformat(),
        "maintenance_due": as_of >= due,
    }


def build_task_qa_report(
    tasks: Iterable[object],
    records: Iterable[Mapping[str, Any]],
    automated_validation: Mapping[str, Any],
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    tasks_list = list(tasks)
    registry = validate_task_qa_records(tasks_list, records)
    automated = _automated_by_task(automated_validation)
    report_date = as_of or date.today()
    rows: list[dict[str, Any]] = []
    stable_contract_errors: list[dict[str, str]] = []
    for record in registry["records"]:
        task_id = str(record["task_id"])
        automated_ready = bool(automated.get(task_id, False))
        aging = _audit_age(record, report_date)
        promotion_ready = bool(
            automated_ready
            and record["manual_reviews_ready"]
            and not record["known_issues"]
            and not aging["maintenance_due"]
            and record["lifecycle"] != "retired"
        )
        row = {
            **record,
            **aging,
            "automated_validation_ready": automated_ready,
            "promotion_ready": promotion_ready,
        }
        rows.append(row)
        if record["lifecycle"] == "stable" and not promotion_ready:
            stable_contract_errors.append(
                {
                    "task_id": task_id,
                    "error": "stable task does not satisfy current automated/manual/aging promotion prerequisites",
                }
            )
    return {
        "schema": QA_REPORT_SCHEMA,
        "as_of": report_date.isoformat(),
        "review_interval_days": QA_REVIEW_INTERVAL_DAYS,
        "ok": bool(
            registry["registry_ok"]
            and automated_validation.get("ok")
            and not stable_contract_errors
        ),
        "registry_ok": registry["registry_ok"],
        "automated_validation_ok": bool(automated_validation.get("ok")),
        "all_promotion_ready": bool(rows) and all(row["promotion_ready"] for row in rows),
        "promotion_ready_count": sum(bool(row["promotion_ready"]) for row in rows),
        "maintenance_due_count": sum(bool(row["maintenance_due"]) for row in rows),
        "task_count": len(tasks_list),
        "tasks": rows,
        "errors": [*registry["errors"], *stable_contract_errors],
    }


__all__ = [
    "EXPOSURE_LEVELS",
    "LIFECYCLES",
    "QA_REPORT_SCHEMA",
    "QA_REVIEW_INTERVAL_DAYS",
    "QA_SCHEMA",
    "REVIEW_KEYS",
    "REVIEW_STATUSES",
    "TaskQAError",
    "build_task_qa_report",
    "load_task_qa",
    "task_semantic_digest",
    "task_semantic_payload",
    "validate_task_qa_records",
]
