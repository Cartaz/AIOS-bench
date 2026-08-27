from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from aios_bench.tasks import load_tasks
from core.benchmark.task_qa import (
    QA_REVIEW_INTERVAL_DAYS,
    build_task_qa_report,
    load_task_qa,
    task_semantic_digest,
    validate_task_qa_records,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DATE = date(2026, 8, 27)


def _reviews(status: str = "pending") -> dict:
    evidence = "review evidence" if status != "pending" else None
    return {
        key: {"status": status, "evidence": evidence}
        for key in (
            "ambiguity_oracle_review",
            "cheat_adversarial_review",
            "multi_agent_pilot",
            "contamination_review",
            "saturation_review",
        )
    }


def _task(task_id: str = "task_a", revision: int = 4, prompt: str = "Do the task"):
    return SimpleNamespace(
        id=task_id,
        category="autonomy",
        prompt=prompt,
        mode="cold",
        tier=4,
        revision=revision,
        tags=("test",),
        required_capabilities=(),
        depends_on=(),
        acceptance=({"type": "reference", "task_id": task_id},),
        behavioral_acceptance=(),
        trajectory_reference=None,
    )


def _record(
    task=None,
    *,
    task_id: str = "task_a",
    revision: int = 4,
    lifecycle: str = "pilot",
    exposure: str = "public_repository",
) -> dict:
    task = task or _task(task_id=task_id, revision=revision)
    return {
        "task_id": task_id,
        "task_revision": revision,
        "task_semantic_digest": task_semantic_digest(task),
        "lifecycle": lifecycle,
        "exposure": exposure,
        "known_issues": [],
        "audited_at": AUDIT_DATE.isoformat(),
        "reviews": _reviews(),
    }


def _automated(task_id: str = "task_a") -> dict:
    return {
        "ok": True,
        "observations": [{
            "task_id": task_id,
            "same_seed_deterministic": True,
            "different_seed_changes_variant": True,
            "untouched_variant_fails": True,
            "golden_variant_passes": True,
        }],
    }


def test_actual_frontier_v4_qa_registry_covers_every_task_without_claiming_promotion() -> None:
    tasks = load_tasks(ROOT / "benchmarks" / "tasks", "frontier_v4")
    records = load_task_qa(ROOT / "benchmarks" / "qa" / "frontier_v4.json")

    result = validate_task_qa_records(tasks, records)

    assert result["registry_ok"] is True, result["errors"]
    assert result["task_count"] == result["record_count"] == 8
    assert all(item["lifecycle"] == "pilot" for item in result["records"])
    assert all(item["manual_reviews_ready"] is False for item in result["records"])
    assert all(len(item["pending_reviews"]) == 5 for item in result["records"])
    assert all(len(item["task_semantic_digest"]) == 64 for item in result["records"])


def test_registry_rejects_missing_and_stale_records() -> None:
    task_a = _task()
    tasks = [task_a, _task(task_id="task_b")]
    record = _record(task_a, revision=3)

    result = validate_task_qa_records(tasks, [record])

    assert result["registry_ok"] is False
    assert {item["error"] for item in result["errors"]} == {
        "stale task_revision 3; catalog has 4",
        "missing QA record",
    }


def test_same_revision_prompt_change_invalidates_prior_audit_digest() -> None:
    audited = _task(prompt="Original task contract")
    changed = _task(prompt="Changed task contract")
    record = _record(audited)

    result = validate_task_qa_records([changed], [record])

    assert result["registry_ok"] is False
    assert any("stale task_semantic_digest" in item["error"] for item in result["errors"])


def test_same_revision_trajectory_reference_change_invalidates_prior_audit_digest() -> None:
    audited = _task()
    audited.trajectory_reference = {
        "required_event_types": ("file_read",),
        "milestones": ({"id": "inspect", "event_types": ("file_read",)},),
    }
    changed = _task()
    changed.trajectory_reference = {
        "required_event_types": ("file_read", "tool_call"),
        "milestones": (
            {"id": "inspect", "event_types": ("file_read",)},
            {"id": "verify", "event_types": ("tool_call",)},
        ),
    }
    record = _record(audited)

    result = validate_task_qa_records([changed], [record])

    assert result["registry_ok"] is False
    assert any("stale task_semantic_digest" in item["error"] for item in result["errors"])


def test_missing_semantic_digest_is_rejected() -> None:
    task = _task()
    record = _record(task)
    del record["task_semantic_digest"]

    result = validate_task_qa_records([task], [record])

    assert result["registry_ok"] is False
    assert any("task_semantic_digest must be" in item["error"] for item in result["errors"])


def test_invalid_calendar_audit_date_is_rejected() -> None:
    task = _task()
    record = _record(task)
    record["audited_at"] = "2026-02-31"

    result = validate_task_qa_records([task], [record])

    assert result["registry_ok"] is False
    assert any("valid calendar date" in item["error"] for item in result["errors"])


def test_stable_lifecycle_cannot_be_declared_with_pending_reviews() -> None:
    task = _task()
    result = validate_task_qa_records([task], [_record(task, lifecycle="stable")])

    assert result["registry_ok"] is False
    assert any("stable lifecycle requires" in item["error"] for item in result["errors"])


def test_qa_report_keeps_valid_pilot_green_without_faking_promotion_readiness() -> None:
    task = _task()

    result = build_task_qa_report(
        [task],
        [_record(task)],
        _automated(),
        as_of=AUDIT_DATE,
    )

    assert result["schema"] == "aios-bench/task-qa-report/v3"
    assert result["ok"] is True
    assert result["promotion_ready_count"] == 0
    assert result["maintenance_due_count"] == 0
    assert result["all_promotion_ready"] is False
    assert result["tasks"][0]["automated_validation_ready"] is True
    assert result["tasks"][0]["manual_reviews_ready"] is False
    assert result["tasks"][0]["audit_age_days"] == 0
    assert result["tasks"][0]["automated_checks"] == {
        "same_seed_deterministic": "passed",
        "different_seed_changes_variant": "passed",
        "negative_baseline_fails": "passed",
        "golden_witness_passes": "passed",
    }
    assert result["tasks"][0]["automated_missing_checks"] == []
    assert result["tasks"][0]["automated_failed_checks"] == []
    assert result["tasks"][0]["contamination_risk"] == "high"
    assert result["contamination_risk_counts"] == {
        "low": 0,
        "medium": 0,
        "high": 1,
        "unknown": 0,
    }


def test_missing_automated_observation_is_explicit_not_inferred_as_failure() -> None:
    task = _task()

    result = build_task_qa_report(
        [task],
        [_record(task)],
        {"ok": True, "observations": []},
        as_of=AUDIT_DATE,
    )

    row = result["tasks"][0]
    assert row["automated_validation_ready"] is False
    assert row["automated_failed_checks"] == []
    assert row["automated_missing_checks"] == [
        "same_seed_deterministic",
        "different_seed_changes_variant",
        "negative_baseline_fails",
        "golden_witness_passes",
    ]
    assert set(row["automated_checks"].values()) == {"missing"}


def test_failed_automated_check_identifies_exact_promotion_blocker() -> None:
    task = _task()
    validation = _automated()
    validation["observations"][0]["different_seed_changes_variant"] = False

    result = build_task_qa_report(
        [task],
        [_record(task)],
        validation,
        as_of=AUDIT_DATE,
    )

    row = result["tasks"][0]
    assert row["automated_validation_ready"] is False
    assert row["automated_failed_checks"] == ["different_seed_changes_variant"]
    assert row["automated_checks"]["different_seed_changes_variant"] == "failed"


def test_contamination_risk_is_derived_from_existing_exposure_source_of_truth() -> None:
    tasks = [_task("private_task"), _task("limited_task"), _task("public_task")]
    records = [
        _record(tasks[0], task_id="private_task", exposure="private"),
        _record(tasks[1], task_id="limited_task", exposure="limited"),
        _record(tasks[2], task_id="public_task", exposure="public_repository"),
    ]
    validation = {
        "ok": True,
        "observations": [
            {**_automated(task.id)["observations"][0]}
            for task in tasks
        ],
    }

    result = build_task_qa_report(tasks, records, validation, as_of=AUDIT_DATE)

    risks = {row["task_id"]: row["contamination_risk"] for row in result["tasks"]}
    assert risks == {
        "private_task": "low",
        "limited_task": "medium",
        "public_task": "high",
    }
    assert result["contamination_risk_counts"] == {
        "low": 1,
        "medium": 1,
        "high": 1,
        "unknown": 0,
    }


def test_stable_promotion_requires_automated_manual_and_fresh_evidence() -> None:
    task = _task()
    record = _record(task, lifecycle="stable")
    record["reviews"] = _reviews("passed")

    result = build_task_qa_report(
        [task],
        [record],
        _automated(),
        as_of=AUDIT_DATE,
    )

    assert result["ok"] is True
    assert result["all_promotion_ready"] is True
    assert result["tasks"][0]["promotion_ready"] is True
    assert result["tasks"][0]["maintenance_due"] is False


def test_expired_pilot_audit_is_maintenance_due_without_breaking_registry_qa() -> None:
    task = _task()
    as_of = date.fromordinal(AUDIT_DATE.toordinal() + QA_REVIEW_INTERVAL_DAYS)

    result = build_task_qa_report(
        [task],
        [_record(task)],
        _automated(),
        as_of=as_of,
    )

    assert result["ok"] is True
    assert result["maintenance_due_count"] == 1
    assert result["tasks"][0]["maintenance_due"] is True
    assert result["tasks"][0]["promotion_ready"] is False


def test_expired_stable_audit_breaks_current_promotion_contract() -> None:
    task = _task()
    record = _record(task, lifecycle="stable")
    record["reviews"] = _reviews("passed")
    as_of = date.fromordinal(AUDIT_DATE.toordinal() + QA_REVIEW_INTERVAL_DAYS)

    result = build_task_qa_report(
        [task],
        [record],
        _automated(),
        as_of=as_of,
    )

    assert result["ok"] is False
    assert result["maintenance_due_count"] == 1
    assert result["tasks"][0]["promotion_ready"] is False
    assert any("aging promotion prerequisites" in item["error"] for item in result["errors"])
