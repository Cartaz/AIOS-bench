from pathlib import Path
from types import SimpleNamespace

import pytest

from aios_bench import cli
from aios_bench.config import AGENTS
from aios_bench.frontier_v4_runner import FrontierV4Runner
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"


def _args(**overrides):
    values = {
        "v4_expense_rows": 48,
        "v4_expense_malformed": 2,
        "v4_expense_distractors": 3,
        "v4_expense_months": 6,
        "v4_config_chain_depth": 3,
        "v4_config_distractors": 3,
        "v4_config_extra_settings": 2,
        "v4_stateful_entities": 24,
        "v4_stateful_mutations": 5,
        "v4_stateful_policy_distractors": 3,
        "v4_stateful_negative_constraints": 4,
        "v4_dependency_entities": 30,
        "v4_dependency_accounts": 12,
        "v4_dependency_mutations": 5,
        "v4_dependency_policy_distractors": 3,
        "v4_dependency_negative_constraints": 6,
        "v4_lineage_depth": 4,
        "v4_lineage_branches": 3,
        "v4_lineage_stale_revisions": 2,
        "v4_lineage_distractors": 4,
        "v4_lineage_extra_settings": 2,
        "v4_tool_cases": 24,
        "v4_tool_actions": 5,
        "v4_tool_distractors": 4,
        "v4_tool_transient_failures": 3,
        "v4_tool_incomplete_responses": 8,
        "v4_retrieval_corpus_size": 96,
        "v4_retrieval_targets": 12,
        "v4_retrieval_duplicates": 12,
        "v4_retrieval_conflicts": 10,
        "v4_retrieval_source_depth": 3,
        "v4_cross_rows": 72,
        "v4_cross_groups": 6,
        "v4_cross_excluded": 12,
        "v4_cross_adjustments": 8,
        "v4_cross_distractors": 3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _runner(results: Path, parameters: dict[str, dict[str, int]]) -> FrontierV4Runner:
    return FrontierV4Runner(
        ROOT,
        AGENTS["piagent"],
        results,
        task_timeout=1,
        total_timeout=None,
        model="test",
        run_id=results.name,
        variant_base_seed=42,
        parametric_parameters=parameters,
    )


def test_v4_parameters_include_every_active_family():
    parameters = cli._v4_parameters(_args())

    assert parameters == {
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
    }


def test_v4_config_pressure_is_configurable():
    parameters = cli._v4_parameters(
        _args(v4_config_chain_depth=6, v4_config_distractors=10, v4_config_extra_settings=5)
    )

    assert parameters["config_traversal"] == {
        "chain_depth": 6,
        "distractor_files": 10,
        "extra_settings": 5,
    }


def test_v4_config_pressure_rejects_invalid_coordinates():
    with pytest.raises(SystemExit, match="invalid Frontier v4 config pressure"):
        cli._v4_parameters(_args(v4_config_chain_depth=1))


def test_v4_stateful_pressure_is_configurable():
    parameters = cli._v4_parameters(
        _args(
            v4_stateful_entities=40,
            v4_stateful_mutations=8,
            v4_stateful_policy_distractors=6,
            v4_stateful_negative_constraints=10,
        )
    )

    assert parameters["stateful_world"] == {
        "entity_count": 40,
        "required_mutations": 8,
        "distractor_policies": 6,
        "negative_constraints": 10,
    }


def test_v4_stateful_pressure_rejects_invalid_coordinates():
    with pytest.raises(SystemExit, match="invalid Frontier v4 stateful pressure"):
        cli._v4_parameters(_args(v4_stateful_entities=4))


def test_v4_dependency_pressure_is_configurable():
    parameters = cli._v4_parameters(
        _args(
            v4_dependency_entities=44,
            v4_dependency_accounts=18,
            v4_dependency_mutations=7,
            v4_dependency_policy_distractors=5,
            v4_dependency_negative_constraints=10,
        )
    )

    assert parameters["dependency_world"] == {
        "entity_count": 44,
        "account_count": 18,
        "required_mutations": 7,
        "distractor_policies": 5,
        "negative_constraints": 10,
    }


def test_v4_dependency_pressure_rejects_invalid_coordinates():
    with pytest.raises(SystemExit, match="invalid Frontier v4 dependency pressure"):
        cli._v4_parameters(_args(v4_dependency_accounts=2))


def test_v4_lineage_pressure_is_configurable():
    parameters = cli._v4_parameters(
        _args(
            v4_lineage_depth=6,
            v4_lineage_branches=5,
            v4_lineage_stale_revisions=4,
            v4_lineage_distractors=9,
            v4_lineage_extra_settings=5,
        )
    )

    assert parameters["workspace_lineage"] == {
        "lineage_depth": 6,
        "branch_count": 5,
        "stale_revisions": 4,
        "distractor_files": 9,
        "extra_settings": 5,
    }


def test_v4_lineage_pressure_rejects_invalid_coordinates():
    with pytest.raises(SystemExit, match="invalid Frontier v4 lineage pressure"):
        cli._v4_parameters(_args(v4_lineage_depth=2))


def test_v4_tool_recovery_pressure_is_configurable():
    parameters = cli._v4_parameters(
        _args(
            v4_tool_cases=48,
            v4_tool_actions=10,
            v4_tool_distractors=12,
            v4_tool_transient_failures=9,
            v4_tool_incomplete_responses=16,
        )
    )

    assert parameters["tool_recovery"] == {
        "case_count": 48,
        "required_actions": 10,
        "distractor_tools": 12,
        "transient_failures": 9,
        "incomplete_responses": 16,
    }


def test_v4_tool_recovery_pressure_rejects_invalid_coordinates():
    with pytest.raises(SystemExit, match="invalid Frontier v4 tool recovery pressure"):
        cli._v4_parameters(_args(v4_tool_actions=20))


def test_v4_retrieval_pressure_is_configurable():
    parameters = cli._v4_parameters(
        _args(
            v4_retrieval_corpus_size=160,
            v4_retrieval_targets=20,
            v4_retrieval_duplicates=30,
            v4_retrieval_conflicts=18,
            v4_retrieval_source_depth=5,
        )
    )

    assert parameters["wide_retrieval"] == {
        "corpus_size": 160,
        "target_count": 20,
        "duplicate_records": 30,
        "conflict_records": 18,
        "source_depth": 5,
    }


def test_v4_retrieval_pressure_rejects_invalid_coordinates():
    with pytest.raises(SystemExit, match="invalid Frontier v4 retrieval pressure"):
        cli._v4_parameters(_args(v4_retrieval_corpus_size=12))


def test_v4_cross_artifact_pressure_is_configurable():
    parameters = cli._v4_parameters(
        _args(
            v4_cross_rows=120,
            v4_cross_groups=9,
            v4_cross_excluded=20,
            v4_cross_adjustments=14,
            v4_cross_distractors=7,
        )
    )

    assert parameters["cross_artifact"] == {
        "row_count": 120,
        "group_count": 9,
        "excluded_rows": 20,
        "adjustment_rows": 14,
        "distractor_files": 7,
    }


def test_v4_cross_artifact_pressure_rejects_invalid_coordinates():
    with pytest.raises(SystemExit, match="invalid Frontier v4 cross-artifact pressure"):
        cli._v4_parameters(_args(v4_cross_rows=12))


def test_skill_ablation_expands_to_both_conditions():
    args = SimpleNamespace(skill_ablation=True, skill_mode="curated_skill")
    assert cli._execution_skill_modes(args) == ("no_skill", "curated_skill")


def test_single_skill_condition_is_preserved():
    args = SimpleNamespace(skill_ablation=False, skill_mode="curated_skill")
    assert cli._execution_skill_modes(args) == ("curated_skill",)


def test_config_pressure_changes_execution_fingerprint_not_landscape_profile(tmp_path: Path):
    baseline = cli._v4_parameters(_args())
    pressured = cli._v4_parameters(
        _args(v4_config_chain_depth=6, v4_config_distractors=10, v4_config_extra_settings=5)
    )
    first = _runner(tmp_path / "first", baseline)
    second = _runner(tmp_path / "second", pressured)

    assert first.execution_fingerprint != second.execution_fingerprint
    assert first.landscape_execution_fingerprint == second.landscape_execution_fingerprint


def test_config_variant_identity_records_effective_pressure(tmp_path: Path):
    parameters = cli._v4_parameters(
        _args(v4_config_chain_depth=5, v4_config_distractors=7, v4_config_extra_settings=4)
    )
    runner = _runner(tmp_path / "identity", parameters)
    task = next(
        task for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "tool_use_config_001"
    )

    runner._workspace(task)
    identity = runner._result_identity(task)

    assert identity["variant_family"] == "config_traversal"
    assert identity["variant_parameters"] == {
        "chain_depth": 5,
        "distractor_files": 7,
        "extra_settings": 4,
    }
    assert identity["variant_digest"]


def test_stateful_variant_identity_records_effective_pressure(tmp_path: Path):
    parameters = cli._v4_parameters(
        _args(
            v4_stateful_entities=36,
            v4_stateful_mutations=7,
            v4_stateful_policy_distractors=5,
            v4_stateful_negative_constraints=9,
        )
    )
    runner = _runner(tmp_path / "stateful-identity", parameters)
    task = next(
        task for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "stateful_support_001"
    )

    runner._workspace(task)
    identity = runner._result_identity(task)

    assert identity["variant_family"] == "stateful_world"
    assert identity["variant_parameters"] == {
        "entity_count": 36,
        "required_mutations": 7,
        "distractor_policies": 5,
        "negative_constraints": 9,
    }
    assert identity["variant_digest"]


def test_dependency_variant_identity_records_effective_pressure(tmp_path: Path):
    parameters = cli._v4_parameters(
        _args(
            v4_dependency_entities=42,
            v4_dependency_accounts=17,
            v4_dependency_mutations=7,
            v4_dependency_policy_distractors=4,
            v4_dependency_negative_constraints=9,
        )
    )
    runner = _runner(tmp_path / "dependency-identity", parameters)
    task = next(
        task for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "support_dependency_001"
    )

    runner._workspace(task)
    identity = runner._result_identity(task)

    assert identity["variant_family"] == "dependency_world"
    assert identity["variant_parameters"] == {
        "entity_count": 42,
        "account_count": 17,
        "required_mutations": 7,
        "distractor_policies": 4,
        "negative_constraints": 9,
    }
    assert identity["variant_digest"]


def test_lineage_variant_identity_records_effective_pressure(tmp_path: Path):
    parameters = cli._v4_parameters(
        _args(
            v4_lineage_depth=6,
            v4_lineage_branches=5,
            v4_lineage_stale_revisions=4,
            v4_lineage_distractors=8,
            v4_lineage_extra_settings=5,
        )
    )
    runner = _runner(tmp_path / "lineage-identity", parameters)
    task = next(
        task for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "tool_use_lineage_001"
    )

    runner._workspace(task)
    identity = runner._result_identity(task)

    assert identity["variant_family"] == "workspace_lineage"
    assert identity["variant_parameters"] == {
        "lineage_depth": 6,
        "branch_count": 5,
        "stale_revisions": 4,
        "distractor_files": 8,
        "extra_settings": 5,
    }
    assert identity["variant_digest"]


def test_tool_recovery_variant_identity_records_effective_pressure(tmp_path: Path):
    parameters = cli._v4_parameters(
        _args(
            v4_tool_cases=40,
            v4_tool_actions=8,
            v4_tool_distractors=10,
            v4_tool_transient_failures=7,
            v4_tool_incomplete_responses=14,
        )
    )
    runner = _runner(tmp_path / "tool-recovery-identity", parameters)
    task = next(
        task for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "tool_recovery_001"
    )

    runner._workspace(task)
    identity = runner._result_identity(task)

    assert identity["variant_family"] == "tool_recovery"
    assert identity["variant_parameters"] == {
        "case_count": 40,
        "required_actions": 8,
        "distractor_tools": 10,
        "transient_failures": 7,
        "incomplete_responses": 14,
    }
    assert identity["variant_digest"]


def test_retrieval_variant_identity_records_effective_pressure(tmp_path: Path):
    parameters = cli._v4_parameters(
        _args(
            v4_retrieval_corpus_size=144,
            v4_retrieval_targets=18,
            v4_retrieval_duplicates=24,
            v4_retrieval_conflicts=16,
            v4_retrieval_source_depth=4,
        )
    )
    runner = _runner(tmp_path / "retrieval-identity", parameters)
    task = next(
        task for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "retrieval_wide_001"
    )

    runner._workspace(task)
    identity = runner._result_identity(task)

    assert identity["variant_family"] == "wide_retrieval"
    assert identity["variant_parameters"] == {
        "corpus_size": 144,
        "target_count": 18,
        "duplicate_records": 24,
        "conflict_records": 16,
        "source_depth": 4,
    }
    assert identity["variant_digest"]


def test_cross_artifact_variant_identity_records_effective_pressure(tmp_path: Path):
    parameters = cli._v4_parameters(
        _args(
            v4_cross_rows=108,
            v4_cross_groups=8,
            v4_cross_excluded=18,
            v4_cross_adjustments=12,
            v4_cross_distractors=5,
        )
    )
    runner = _runner(tmp_path / "cross-artifact-identity", parameters)
    task = next(
        task for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "data_cross_artifact_001"
    )

    runner._workspace(task)
    identity = runner._result_identity(task)

    assert identity["variant_family"] == "cross_artifact"
    assert identity["variant_parameters"] == {
        "row_count": 108,
        "group_count": 8,
        "excluded_rows": 18,
        "adjustment_rows": 12,
        "distractor_files": 5,
    }
    assert identity["variant_digest"]
