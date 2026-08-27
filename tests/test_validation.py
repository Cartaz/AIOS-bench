from pathlib import Path
from types import SimpleNamespace

from aios_bench.tasks import load_tasks
from aios_bench.validation import validate_negative_baseline, validate_parametric_baseline


ROOT = Path(__file__).resolve().parents[1]


def _repo(tmp_path: Path, *, solved: bool) -> Path:
    workspace = tmp_path / "benchmarks" / "fixtures" / "workspace"
    workspace.mkdir(parents=True)
    if solved:
        (workspace / "answer.txt").write_text("already solved", encoding="utf-8")
    return tmp_path


def _task():
    return SimpleNamespace(
        id="test_task",
        acceptance=({"type": "exists", "path": "answer.txt", "weight": 1, "fatal": True},),
    )


def test_negative_preflight_accepts_unsolved_fixture(tmp_path: Path):
    result = validate_negative_baseline(_repo(tmp_path, solved=False), [_task()])
    assert result["ok"] is True
    assert result["checked_tasks"] == 1
    assert result["failures"] == []


def test_negative_preflight_rejects_fixture_that_already_passes(tmp_path: Path):
    result = validate_negative_baseline(_repo(tmp_path, solved=True), [_task()])
    assert result["ok"] is False
    assert result["failures"][0]["reason"] == "untouched fixture passes grader"


def test_parametric_preflight_checks_all_catalog_families():
    tasks = load_tasks(ROOT / "benchmarks" / "tasks", "frontier_v4")
    result = validate_parametric_baseline(
        ROOT,
        tasks,
        base_seed=42,
        parameters={
            "expense_report": {
                "rows": 32,
                "malformed_rows": 2,
                "distractor_files": 1,
                "months": 4,
            },
            "config_traversal": {
                "chain_depth": 4,
                "distractor_files": 2,
                "extra_settings": 3,
            },
            "causal_gateway": {
                "distractor_logs": 3,
                "extra_services": 2,
            },
            "runtime_investigation": {
                "lanes": 5,
                "distractor_docs": 3,
            },
            "tool_branching": {
                "distractor_tools": 4,
            },
            "coverage_migration": {
                "targets": 7,
                "current_active": 2,
                "historical_decoys": 4,
            },
        },
    )

    assert result["ok"] is True, result["failures"]
    assert result["checked_tasks"] == 6
    assert {item["family"] for item in result["observations"]} == {
        "expense_report",
        "config_traversal",
        "causal_gateway",
        "runtime_investigation",
        "tool_branching",
        "coverage_migration",
    }
    for observation in result["observations"]:
        assert observation["same_seed_deterministic"] is True
        assert observation["different_seed_changes_variant"] is True
        assert observation["untouched_variant_fails"] is True
        assert observation["golden_variant_passes"] is True
        assert observation["variant_digest"] != observation["comparison_variant_digest"]
