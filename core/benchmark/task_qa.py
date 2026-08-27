from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping


QA_SCHEMA = "aios-bench/task-qa/v4"
QA_REPORT_SCHEMA = "aios-bench/task-qa-report/v5"
QA_REVIEW_INTERVAL_DAYS = 180
LIFECYCLES = frozenset({"draft", "pilot", "stable", "retired"})
REVIEW_STATUSES = frozenset({"pending", "passed", "failed", "not_applicable"})
REVIEW_EVIDENCE_KINDS = frozenset({
    "manual_review",
    "ci_run",
    "benchmark_run",
    "document",
    "external_reference",
})
REVIEW_KEYS = (
    "ambiguity_oracle_review",
    "cheat_adversarial_review",
    "multi_agent_pilot",
    "contamination_review",
    "saturation_review",
)
EXPOSURE_LEVELS = frozenset({"private", "limited", "public_repository"})
CONTAMINATION_RISK_BY_EXPOSURE = {
    "private": "low",
    "limited": "medium",
    "public_repository": "high",
}
AUTOMATED_CHECK_KEYS = (
    "same_seed_deterministic",
    "different_seed_changes_variant",
    "negative_baseline_fails",
    "golden_witness_passes",
)
_SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def review_context_digest(task_digest: str, exposure: str) -> str:
    """Bind manual review evidence to task meaning plus its exposure state."""
    payload = json.dumps(
        {
            "task_semantic_digest": str(task_digest),
            "exposure": str(exposure),
        },
        sort_keys=True,
        separators=(",", ":"),
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


def _valid_date(value: object) -> bool:
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _review_evidence_errors(key: str, status: str, evidence: object) -> list[str]:
    if status == "pending":
        return [] if evidence is None else [f"{key} pending status requires evidence=null"]
    if not isinstance(evidence, Mapping):
        return [f"{key} status {status} requires structured evidence"]

    errors: list[str] = []
    allowed = {"kind", "reference", "observed_at", "notes"}
    unknown = sorted(set(str(item) for item in evidence) - allowed)
    if unknown:
        errors.append(f"{key} evidence has unknown keys: {unknown}")
    kind = str(evidence.get("kind", ""))
    if kind not in REVIEW_EVIDENCE_KINDS:
        errors.append(f"{key} evidence has invalid kind {kind!r}")
    reference = evidence.get("reference")
    if not isinstance(reference, str) or not reference.strip():
        errors.append(f"{key} evidence reference must be a non-empty string")
    observed_at = evidence.get("observed_at")
    if not _valid_date(observed_at):
        errors.append(f"{key} evidence observed_at must be a valid YYYY-MM-DD date")
    notes = evidence.get("notes")
    if notes is not None and (not isinstance(notes, str) or not notes.strip()):
        errors.append(f"{key} evidence notes must be null or a non-empty string")
    return errors


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
        if status not in REVIEW_STATUSES:
            errors.append(f"{key} has invalid status {status!r}")
            continue
        errors.extend(_review_evidence_errors(key, status, raw.get("evidence")))
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

        context_digest = str(raw.get("review_context_digest", ""))
        if not _SHA256.fullmatch(context_digest):
            record_errors.append("review_context_digest must be a lowercase SHA-256 hex digest")
        elif _SHA256.fullmatch(semantic_digest) and exposure in EXPOSURE_LEVELS:
            expected_context = review_context_digest(semantic_digest, exposure)
            if context_digest != expected_context:
                record_errors.append(
                    f"stale review_context_digest {context_digest}; current context has {expected_context}"
                )

        known_issues = raw.get("known_issues")
        if not isinstance(known_issues, list) or not all(
            isinstance(item, str) and item.strip() for item in known_issues
        ):
            record_errors.append("known_issues must be an array of non-empty strings")
            known_issues = []
        audited_at = raw.get("audited_at")
        if not _valid_date(audited_at):
            record_errors.append("audited_at must be a valid YYYY-MM-DD date")
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
            "review_context_digest": context_digest,
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


def _status(value: object) -> str:
    if value is True:
        return "passed"
    if value is False:
        return "failed"
    return "missing"


def _automated_evidence_by_task(validation: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    observations = validation.get("observations")
    if not isinstance(observations, list):
        return result
    for item in observations:
        if not isinstance(item, Mapping) or not item.get("task_id"):
            continue
        task_id = str(item["task_id"])
        if "same_seed_deterministic" in item:
            checks = {
                "same_seed_deterministic": _status(item.get("same_seed_deterministic")),
                "different_seed_changes_variant": _status(item.get("different_seed_changes_variant")),
                "negative_baseline_fails": _status(item.get("untouched_variant_fails")),
                "golden_witness_passes": _status(item.get("golden_variant_passes")),
            }
        else:
            checks = {
                "same_seed_deterministic": "not_applicable",
                "different_seed_changes_variant": "not_applicable",
                "negative_baseline_fails": _status(item.get("untouched_fixture_fails")),
                "golden_witness_passes": _status(item.get("golden_solution_passes")),
            }
        missing = [key for key in AUTOMATED_CHECK_KEYS if checks[key] == "missing"]
        failed = [key for key in AUTOMATED_CHECK_KEYS if checks[key] == "failed"]
        result[task_id] = {
            "checks": checks,
            "missing_checks": missing,
            "failed_checks": failed,
            "ready": not missing and not failed,
        }
    return result


def _missing_automated_evidence() -> dict[str, Any]:
    return {
        "checks": {key: "missing" for key in AUTOMATED_CHECK_KEYS},
        "missing_checks": list(AUTOMATED_CHECK_KEYS),
        "failed_checks": [],
        "ready": False,
    }


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
    automated = _automated_evidence_by_task(automated_validation)
    report_date = as_of or date.today()
    rows: list[dict[str, Any]] = []
    stable_contract_errors: list[dict[str, str]] = []
    for record in registry["records"]:
        task_id = str(record["task_id"])
        evidence = automated.get(task_id, _missing_automated_evidence())
        automated_ready = bool(evidence["ready"])
        aging = _audit_age(record, report_date)
        contamination_risk = CONTAMINATION_RISK_BY_EXPOSURE.get(
            str(record["exposure"]),
            "unknown",
        )
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
            "contamination_risk": contamination_risk,
            "automated_checks": dict(evidence["checks"]),
            "automated_missing_checks": list(evidence["missing_checks"]),
            "automated_failed_checks": list(evidence["failed_checks"]),
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
    risk_counts = {
        risk: sum(row["contamination_risk"] == risk for row in rows)
        for risk in ("low", "medium", "high", "unknown")
    }
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
        "contamination_risk_counts": risk_counts,
        "task_count": len(tasks_list),
        "tasks": rows,
        "errors": [*registry["errors"], *stable_contract_errors],
    }


__all__ = [
    "AUTOMATED_CHECK_KEYS",
    "CONTAMINATION_RISK_BY_EXPOSURE",
    "EXPOSURE_LEVELS",
    "LIFECYCLES",
    "QA_REPORT_SCHEMA",
    "QA_REVIEW_INTERVAL_DAYS",
    "QA_SCHEMA",
    "REVIEW_EVIDENCE_KINDS",
    "REVIEW_KEYS",
    "REVIEW_STATUSES",
    "TaskQAError",
    "build_task_qa_report",
    "load_task_qa",
    "review_context_digest",
    "task_semantic_digest",
    "task_semantic_payload",
    "validate_task_qa_records",
]
