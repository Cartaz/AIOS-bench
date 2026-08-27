from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.benchmark.task_qa import (
    build_task_qa_report,
    load_task_qa,
    validate_task_qa_records,
)
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]


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


def _record(task_id: str = "task_a", revision: int = 4, lifecycle: str = "pilot") -> dict:
    return {
        "task_id": task_id,
        "task_revision": revision,
        "lifecycle": lifecycle,
        "exposure": "public_repository",
        "known_issues": [],
        "audited_at": "2026-08-27",
        "reviews": _reviews(),
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


def test_registry_rejects_missing_and_stale_records() -> None:
    tasks = [SimpleNamespace(id="task_a", revision=4), SimpleNamespace(id="task_b", revision=4)]
    result = validate_task_qa_records(tasks, [_record(revision=3)])

    assert result["registry_ok"] is False
    assert {item["error"] for item in result["errors"]} == {
        "stale task_revision 3; catalog has 4",
        "missing QA record",
    }


def test_stable_lifecycle_cannot_be_declared_with_pending_reviews() -> None:
    tasks = [SimpleNamespace(id="task_a", revision=4)]
    result = validate_task_qa_records(tasks, [_record(lifecycle="stable")])

    assert result["registry_ok"] is False
    assert any("stable lifecycle requires" in item["error"] for item in result["errors"])


def test_qa_report_keeps_valid_pilot_green_without_faking_promotion_readiness() -> None:
    tasks = [SimpleNamespace(id="task_a", revision=4)]
    automated = {
        "ok": True,
        "observations": [{
            "task_id": "task_a",
            "same_seed_deterministic": True,
            "different_seed_changes_variant": True,
            "untouched_variant_fails": True,
            "golden_variant_passes": True,
        }],
    }

    result = build_task_qa_report(tasks, [_record()], automated)

    assert result["ok"] is True
    assert result["promotion_ready_count"] == 0
    assert result["all_promotion_ready"] is False
    assert result["tasks"][0]["automated_validation_ready"] is True
    assert result["tasks"][0]["manual_reviews_ready"] is False


def test_stable_promotion_requires_automated_and_manual_evidence() -> None:
    tasks = [SimpleNamespace(id="task_a", revision=4)]
    record = _record(lifecycle="stable")
    record["reviews"] = _reviews("passed")
    automated = {
        "ok": True,
        "observations": [{
            "task_id": "task_a",
            "same_seed_deterministic": True,
            "different_seed_changes_variant": True,
            "untouched_variant_fails": True,
            "golden_variant_passes": True,
        }],
    }

    result = build_task_qa_report(tasks, [record], automated)

    assert result["ok"] is True
    assert result["all_promotion_ready"] is True
    assert result["tasks"][0]["promotion_ready"] is True
