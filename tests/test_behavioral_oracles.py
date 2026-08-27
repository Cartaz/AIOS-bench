from __future__ import annotations

from pathlib import Path

import pytest

from core.benchmark.behavioral_oracles import (
    BehavioralOracleError,
    capture_behavioral_baseline,
    evaluate_behavioral_oracles,
    validate_behavioral_checks,
)


def test_behavioral_oracles_cover_required_forbidden_preserved_and_evidence(tmp_path: Path) -> None:
    (tmp_path / "config.txt").write_text("mode=old\n", encoding="utf-8")
    (tmp_path / "decoy.log").write_text("historical warning\n", encoding="utf-8")
    checks = [
        {"type": "required_state", "path": "result.txt", "contains": "healthy"},
        {"type": "forbidden_state", "path": "result.txt", "contains": "broken"},
        {"type": "preserved_state", "path": "config.txt"},
        {"type": "decoy_untouched", "path": "decoy.log"},
        {"type": "required_evidence", "event_type": "tool_call", "data": {"tool": "probe"}},
    ]
    baseline = capture_behavioral_baseline(tmp_path, checks)
    (tmp_path / "result.txt").write_text("healthy\n", encoding="utf-8")

    result = evaluate_behavioral_oracles(
        tmp_path,
        checks,
        baseline=baseline,
        events=[{"type": "tool_call", "source": "agent", "data": {"tool": "probe", "extra": 1}}],
    )

    assert result["passed"] is True
    assert result["checks_passed"] == 5
    assert result["checks_total"] == 5
    assert result["affects_score"] is False


def test_preservation_detects_changed_or_deleted_state(tmp_path: Path) -> None:
    target = tmp_path / "keep.txt"
    target.write_text("baseline", encoding="utf-8")
    checks = [{"type": "preserved_state", "path": "keep.txt"}]
    baseline = capture_behavioral_baseline(tmp_path, checks)

    target.write_text("changed", encoding="utf-8")
    changed = evaluate_behavioral_oracles(tmp_path, checks, baseline=baseline)
    target.unlink()
    deleted = evaluate_behavioral_oracles(tmp_path, checks, baseline=baseline)

    assert changed["passed"] is False
    assert deleted["passed"] is False


def test_required_evidence_matches_nested_data_subset() -> None:
    result = evaluate_behavioral_oracles(
        Path("."),
        [{
            "type": "required_evidence",
            "event_type": "tool_result",
            "source": "piagent",
            "data": {"result": {"status": 200}},
        }],
        events=[{
            "type": "tool_result",
            "source": "piagent",
            "data": {"result": {"status": 200, "body": "ok"}, "call_id": "1"},
        }],
    )

    assert result["passed"] is True


def test_behavioral_validation_rejects_unsafe_paths_and_ambiguous_predicates() -> None:
    with pytest.raises(BehavioralOracleError):
        validate_behavioral_checks([{"type": "preserved_state", "path": "../secret"}])
    with pytest.raises(BehavioralOracleError):
        validate_behavioral_checks([
            {"type": "required_state", "path": "x", "contains": "a", "regex": "b"}
        ])
    with pytest.raises(BehavioralOracleError):
        validate_behavioral_checks([{"type": "required_evidence"}])
