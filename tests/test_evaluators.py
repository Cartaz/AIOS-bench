from pathlib import Path
from unittest.mock import patch

from aios_bench.evaluators import evaluate_artifacts
from aios_bench.reference_checks import check_task
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


def test_tool_use_reference_is_routed_to_data_oracle(tmp_path: Path):
    with patch("aios_bench.reference_checks.check_data", return_value=(True, "data oracle")) as data_check, \
            patch("aios_bench.reference_checks.check_system") as system_check:
        result = check_task("tool_use_003", tmp_path, tmp_path)

    assert result == (True, "data oracle")
    data_check.assert_called_once_with("tool_use_003", tmp_path, tmp_path)
    system_check.assert_not_called()


def test_other_tool_use_references_stay_on_system_oracle(tmp_path: Path):
    with patch("aios_bench.reference_checks.check_data") as data_check, \
            patch("aios_bench.reference_checks.check_system", return_value=(True, "system oracle")) as system_check:
        result = check_task("tool_use_002", tmp_path, tmp_path)

    assert result == (True, "system oracle")
    data_check.assert_not_called()
    system_check.assert_called_once_with("tool_use_002", tmp_path, tmp_path, None)


def test_missing_reference_result_becomes_failed_check(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AIOS_BENCH_FIXTURE_ROOT", str(tmp_path))
    with patch("aios_bench.evaluators.check_task", return_value=None):
        result = evaluate_artifacts(tmp_path, [{"type": "reference", "task_id": "future_001"}])

    assert result["passed"] is False
    assert result["results"][0]["passed"] is False
    assert "returned no result" in result["results"][0]["detail"]


def test_reference_oracle_exception_fails_check_without_aborting_suite(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AIOS_BENCH_FIXTURE_ROOT", str(tmp_path))
    with patch("aios_bench.evaluators.check_task", side_effect=RuntimeError("bad artifact")):
        result = evaluate_artifacts(tmp_path, [{"type": "reference", "task_id": "broken"}])
    assert result["passed"] is False
    assert "RuntimeError: bad artifact" in result["results"][0]["detail"]


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


def test_command_checks_do_not_invoke_a_shell(tmp_path: Path):
    marker = tmp_path / "shell-injection"
    result = evaluate_artifacts(tmp_path, [{
        "type": "command",
        "command": f'python -c "raise SystemExit(0)"; touch {marker}',
    }])

    assert result["results"][0]["passed"] is True
    assert not marker.exists()
