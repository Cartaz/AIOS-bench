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
            "causal_gateway": {
                "distractor_logs": 2,
                "extra_services": 2,
            },
            "runtime_investigation": {
                "lanes": 4,
                "distractor_docs": 2,
            },
            "tool_branching": {
                "distractor_tools": 3,
            },
            "coverage_migration": {
                "targets": 8,
                "current_active": 2,
                "historical_decoys": 4,
            },
        },
    )

    assert result["schema"] == "aios-bench/parametric-validation/v2"
    assert result["checked_tasks"] == 6
    assert result["ok"] is True, result["failures"]
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
        assert observation["positive_acceptance_score"] == 1.0
