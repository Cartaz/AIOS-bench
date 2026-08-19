from pathlib import Path

from aios_bench.evaluators import evaluate_artifacts
from aios_bench.reference_checks_subagents import check as check_subagents


def test_weighted_acceptance_supports_partial_scores(tmp_path: Path):
    (tmp_path / "report.md").write_text("Verification\n", encoding="utf-8")
    result = evaluate_artifacts(tmp_path, [
        {"type": "exists", "path": "report.md", "weight": 2, "fatal": True},
        {"type": "contains", "path": "report.md", "text": "Verification", "weight": 1},
        {"type": "contains", "path": "report.md", "text": "Missing", "weight": 1},
    ])
    assert result["checks_passed"] == 2
    assert result["checks_total"] == 3
    assert result["acceptance_score"] == 0.75
    assert result["passed"] is False


def test_json_and_regex_checks(tmp_path: Path):
    (tmp_path / "data.json").write_text('{"status":"ok"}', encoding="utf-8")
    (tmp_path / "report.md").write_text("Result: 42\n", encoding="utf-8")
    result = evaluate_artifacts(tmp_path, [
        {"type": "json_valid", "path": "data.json", "weight": 1},
        {"type": "regex", "path": "report.md", "pattern": r"Result:\s+\d+", "weight": 1},
    ])
    assert result["passed"] is True
    assert result["acceptance_score"] == 1.0


def test_subagent_oracle_requires_normalized_events_not_reported_prose(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "decision_memo.md").write_text(
        "CVE-2026-0001\n## Rejected\nDecision: reject\n",
        encoding="utf-8",
    )

    passed, _ = check_subagents("subagents_002", tmp_path, tmp_path, events=[])
    assert passed is False

    events = [
        {"type": "subagent_start", "data": {"inferred": True}},
        {"type": "subagent_start", "data": {"inferred": True}},
    ]
    passed, _ = check_subagents("subagents_002", tmp_path, tmp_path, events=events)
    assert passed is False

    events = [{"type": "subagent_start"}, {"type": "subagent_start"}]
    passed, _ = check_subagents("subagents_002", tmp_path, tmp_path, events=events)
    assert passed is True
