from dataclasses import replace

from core.benchmark.health import HEALTH_SCHEMA, validate_benchmark_health
from core.benchmark.parametric import normalize_parameters
from core.benchmark.paths import REPO_ROOT, TASKS_ROOT
from core.benchmark.tasks import load_tasks


def _task(task_id: str):
    return next(task for task in load_tasks(TASKS_ROOT, "frontier_v4") if task.id == task_id)


def test_health_gate_checks_generation_oracle_and_grader_contracts() -> None:
    task = _task("autonomy_expense_001")
    result = validate_benchmark_health(
        REPO_ROOT,
        [task],
        base_seed=73,
        parameters=normalize_parameters(),
    )

    assert result["schema"] == HEALTH_SCHEMA
    assert result["ok"] is True, result["failures"]
    assert result["checked_tasks"] == 1
    observation = result["observations"][0]
    assert observation["same_seed_oracle_deterministic"] is True
    assert observation["same_seed_workspace_deterministic"] is True
    assert observation["different_seed_changes_oracle"] is True
    assert observation["different_seed_changes_workspace"] is True
    assert observation["oracle_schema_valid"] is True
    assert observation["oracle_hidden_from_workspace"] is True
    assert observation["protected_sources_intact"] is True
    assert observation["task_contract_consistent"] is True
    assert observation["untouched_variant_fails"] is True
    assert observation["golden_variant_passes"] is True
    assert observation["comparison_seed_golden_passes"] is True
    assert observation["missing_required_artifact_fails"] is True
    assert observation["grader_within_budget"] is True


def test_entire_frontier_v4_catalog_passes_benchmark_health_gate() -> None:
    tasks = load_tasks(TASKS_ROOT, "frontier_v4")
    result = validate_benchmark_health(
        REPO_ROOT,
        tasks,
        base_seed=42,
        parameters=normalize_parameters(),
    )

    assert result["checked_tasks"] == len(tasks)
    assert result["ok"] is True, result["failures"]
    assert not result["failures"]


def test_health_gate_detects_instruction_verifier_drift() -> None:
    task = _task("autonomy_expense_001")
    broken = replace(task, prompt="Produce the required result without naming its output paths.")

    result = validate_benchmark_health(REPO_ROOT, [broken], base_seed=91)

    assert result["ok"] is False
    observation = result["observations"][0]
    assert observation["task_contract_consistent"] is False
    reasons = {item["reason"] for item in result["failures"]}
    assert "task instructions and verifier contract disagree" in reasons


def test_health_gate_rejects_nonpositive_grader_budget() -> None:
    task = _task("autonomy_expense_001")
    try:
        validate_benchmark_health(REPO_ROOT, [task], max_grader_seconds=0)
    except ValueError as exc:
        assert "max_grader_seconds" in str(exc)
    else:
        raise AssertionError("nonpositive grader budget must be rejected")
