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
            "stateful_world": {
                "entity_count": 30,
                "required_mutations": 5,
                "distractor_policies": 2,
                "negative_constraints": 6,
            },
            "dependency_world": {
                "entity_count": 36,
                "account_count": 16,
                "required_mutations": 6,
                "distractor_policies": 3,
                "negative_constraints": 8,
            },
            "workspace_lineage": {
                "lineage_depth": 5,
                "branch_count": 4,
                "stale_revisions": 3,
                "distractor_files": 5,
                "extra_settings": 3,
            },
            "tool_recovery": {
                "case_count": 30,
                "required_actions": 6,
                "distractor_tools": 6,
                "transient_failures": 5,
                "incomplete_responses": 10,
            },
            "wide_retrieval": {
                "corpus_size": 120,
                "target_count": 16,
                "duplicate_records": 18,
                "conflict_records": 14,
                "source_depth": 4,
            },
            "cross_artifact": {
                "row_count": 90,
                "group_count": 7,
                "excluded_rows": 15,
                "adjustment_rows": 10,
                "distractor_files": 4,
            },
            "epistemic_twins": {
                "pair_count": 8,
                "registry_size": 64,
                "distractor_records": 18,
                "archive_revisions": 4,
                "source_depth": 4,
            },
            "black_box_reconstruction": {
                "rule_count": 8,
                "public_examples": 16,
                "probe_budget": 56,
                "distractor_fields": 5,
                "max_units": 700,
            },
        },
    )

    assert result["ok"] is True, result["failures"]
    assert result["checked_tasks"] == 13
    assert {item["family"] for item in result["observations"]} == {
        "expense_report",
        "config_traversal",
        "stateful_world",
        "dependency_world",
        "workspace_lineage",
        "tool_recovery",
        "wide_retrieval",
        "cross_artifact",
        "epistemic_twins",
        "black_box_reconstruction",
        "persistent_memory",
    }
    for observation in result["observations"]:
        assert observation["same_seed_deterministic"] is True
        assert observation["different_seed_changes_variant"] is True
        assert observation["untouched_variant_fails"] is True
        assert observation["golden_variant_passes"] is True
        assert observation["variant_digest"] != observation["comparison_variant_digest"]
