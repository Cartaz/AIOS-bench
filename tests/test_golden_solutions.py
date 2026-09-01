from pathlib import Path

from aios_bench.tasks import load_tasks
from aios_bench.validation import validate_parametric_baseline, validate_static_baseline


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmarks" / "tasks"


def test_every_frontier_v3_grader_rejects_untouched_and_accepts_golden():
    result = validate_static_baseline(ROOT, load_tasks(TASKS, "frontier_v3"))

    assert result["schema"] == "aios-bench/static-validation/v2"
    assert result["checked_tasks"] == 28
    assert result["ok"] is True, result["failures"]
    assert all(item["untouched_fixture_fails"] for item in result["observations"])
    assert all(item["golden_solution_passes"] for item in result["observations"])
    assert all(item["positive_acceptance_score"] == 1.0 for item in result["observations"])


def test_frontier_v4_graders_reject_generated_baseline_and_accept_goldens():
    result = validate_parametric_baseline(
        ROOT,
        load_tasks(TASKS, "frontier_v4"),
        base_seed=42,
        parameters={
            "expense_report": {
                "rows": 48,
                "malformed_rows": 2,
                "distractor_files": 3,
                "months": 6,
            },
            "config_traversal": {
                "chain_depth": 3,
                "distractor_files": 3,
                "extra_settings": 2,
            },
            "stateful_world": {
                "entity_count": 24,
                "required_mutations": 5,
                "distractor_policies": 3,
                "negative_constraints": 4,
            },
            "dependency_world": {
                "entity_count": 30,
                "account_count": 12,
                "required_mutations": 5,
                "distractor_policies": 3,
                "negative_constraints": 6,
            },
            "workspace_lineage": {
                "lineage_depth": 4,
                "branch_count": 3,
                "stale_revisions": 2,
                "distractor_files": 4,
                "extra_settings": 2,
            },
            "tool_recovery": {
                "case_count": 24,
                "required_actions": 5,
                "distractor_tools": 4,
                "transient_failures": 3,
                "incomplete_responses": 8,
            },
            "wide_retrieval": {
                "corpus_size": 96,
                "target_count": 12,
                "duplicate_records": 12,
                "conflict_records": 10,
                "source_depth": 3,
            },
            "cross_artifact": {
                "row_count": 72,
                "group_count": 6,
                "excluded_rows": 12,
                "adjustment_rows": 8,
                "distractor_files": 3,
            },
            "epistemic_twins": {
                "pair_count": 6,
                "registry_size": 48,
                "distractor_records": 12,
                "archive_revisions": 3,
                "source_depth": 3,
            },
            "black_box_reconstruction": {
                "rule_count": 7,
                "public_examples": 12,
                "probe_budget": 48,
                "distractor_fields": 3,
                "max_units": 500,
            },
        },
    )

    assert result["schema"] == "aios-bench/parametric-validation/v2"
    assert result["checked_tasks"] == 16
    assert result["ok"] is True, result["failures"]
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
        "learning_transfer",
    }
    for observation in result["observations"]:
        assert observation["same_seed_deterministic"] is True
        assert observation["different_seed_changes_variant"] is True
        assert observation["untouched_variant_fails"] is True
        assert observation["golden_variant_passes"] is True
        assert observation["positive_acceptance_score"] == 1.0
