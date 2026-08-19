from pathlib import Path

from aios_bench.evaluators import evaluate_artifacts


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
        {"type": "regex", "path": "report.md", "pattern": r"Result:\\s+\\d+", "weight": 1},
    ])
    assert result["passed"] is True
    assert result["acceptance_score"] == 1.0
