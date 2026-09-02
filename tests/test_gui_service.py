from pathlib import Path
from types import SimpleNamespace

import pytest

from core.benchmark.horizon import get_horizon_profile
from core.run_service import BenchmarkService, RunRequest

ROOT = Path(__file__).resolve().parents[1]


def test_gui_catalog_uses_canonical_harness_and_task_sources():
    service = BenchmarkService(ROOT)
    catalog = service.catalog("frontier_v3")
    assert [item["id"] for item in catalog["harnesses"]] == [
        "hermes", "piagent", "opencode", "goose", "letta", "agentzero", "claude", "deepseek"
    ]
    task_ids = {item["id"] for item in catalog["tasks"]}
    assert "autonomy_001" in task_ids
    assert "tool_use_003" in task_ids
    assert catalog["skill_modes"] == []
    assert catalog["horizon_profiles"] == []


def test_gui_catalog_switches_suite_without_mixing_tasks():
    service = BenchmarkService(ROOT)
    catalog = service.catalog("frontier_v4")
    assert {item["id"] for item in catalog["tasks"]} == {
        "autonomy_expense_001",
        "stateful_support_001",
        "support_dependency_001",
        "data_cross_artifact_001",
        "learning_acquire_001",
        "learning_transfer_001",
        "learning_repair_001",
        "memory_persist_001",
        "memory_persist_002",
        "memory_persist_003",
        "reasoning_epistemic_001",
        "retrieval_wide_001",
        "software_black_box_001",
        "subagents_reconcile_001",
        "tool_use_config_001",
        "tool_use_lineage_001",
        "tool_recovery_001",
    }
    assert catalog["skill_modes"] == ["no_skill", "curated_skill"]
    assert len(catalog["horizon_profiles"]) == 1
    horizon = catalog["horizon_profiles"][0]
    assert horizon["cell_count"] == 15
    assert horizon["task_ids"] == [
        "stateful_support_001",
        "support_dependency_001",
        "tool_use_lineage_001",
        "tool_recovery_001",
        "retrieval_wide_001",
    ]
    assert len(horizon["profile_digest"]) == 64


def test_gui_frontier_v4_runner_records_all_default_pressure_coordinates(tmp_path: Path):
    service = BenchmarkService(ROOT)
    service.results_root = tmp_path / "results"
    request = RunRequest(
        suite="frontier_v4",
        harnesses=("piagent",),
        task_ids=("support_dependency_001",),
        model="test",
    )
    tasks = service.validate_request(request)
    runner = service._build_runner(
        request,
        "piagent",
        "pressure-defaults",
        42,
        lambda event: None,
    )
    try:
        assert runner.suite.parametric is not None
        coordinates = runner.suite.parametric["pressure_coordinates"]
        assert set(coordinates) == {
            "expense_report",
            "config_traversal",
            "stateful_world",
            "dependency_world",
            "workspace_lineage",
            "tool_recovery",
            "wide_retrieval",
            "cross_artifact",
            "delegation_reconciliation",
            "epistemic_twins",
            "black_box_reconstruction",
            "persistent_memory",
            "learning_transfer",
        }
        assert coordinates["dependency_world"] == {
            "entity_count": 30,
            "account_count": 12,
            "required_mutations": 5,
            "distractor_policies": 3,
            "negative_constraints": 6,
        }
        assert coordinates["workspace_lineage"] == {
            "lineage_depth": 4,
            "branch_count": 3,
            "stale_revisions": 2,
            "distractor_files": 4,
            "extra_settings": 2,
        }
        assert coordinates["tool_recovery"] == {
            "case_count": 24,
            "required_actions": 5,
            "distractor_tools": 4,
            "transient_failures": 3,
            "incomplete_responses": 8,
        }
        assert coordinates["wide_retrieval"] == {
            "corpus_size": 96,
            "target_count": 12,
            "duplicate_records": 12,
            "conflict_records": 10,
            "source_depth": 3,
        }
        assert coordinates["cross_artifact"] == {
            "row_count": 72,
            "group_count": 6,
            "excluded_rows": 12,
            "adjustment_rows": 8,
            "distractor_files": 3,
        }
        assert coordinates["delegation_reconciliation"] == {
            "topic_count": 8,
            "conflict_count": 4,
            "distractor_records": 10,
            "fabricated_claims": 2,
        }
        assert coordinates["epistemic_twins"] == {
            "pair_count": 6,
            "registry_size": 48,
            "distractor_records": 12,
            "archive_revisions": 3,
            "source_depth": 3,
        }
        assert coordinates["black_box_reconstruction"] == {
            "rule_count": 7,
            "public_examples": 12,
            "probe_budget": 48,
            "distractor_fields": 3,
            "max_units": 500,
        }
        assert coordinates["persistent_memory"] == {
            "durable_fact_count": 6,
            "transient_fact_count": 3,
            "distractor_fact_count": 4,
            "update_count": 2,
        }
        assert coordinates["learning_transfer"] == {
            "demo_count": 3,
            "rows_per_demo": 54,
            "evaluation_rows": 60,
            "group_count": 6,
            "distractor_columns": 4,
            "schema_shift_fields": 4,
        }
    finally:
        runner.abort(tasks)


def test_gui_request_requires_selected_dependencies():
    service = BenchmarkService(ROOT)
    catalog = service.catalog("frontier_v3")
    dependent = next(item for item in catalog["tasks"] if item["depends_on"])
    request = RunRequest(
        suite="frontier_v3",
        harnesses=("piagent",),
        task_ids=(dependent["id"],),
        model="test",
    )
    with pytest.raises(ValueError, match="requires selected dependencies"):
        service.validate_request(request)


def test_gui_request_rejects_unknown_harness_and_empty_task_selection():
    service = BenchmarkService(ROOT)
    with pytest.raises(ValueError, match="Unknown harnesses"):
        service.validate_request(RunRequest("frontier_v3", ("missing",), ("autonomy_001",), "test"))
    with pytest.raises(ValueError, match="Select at least one task"):
        service.validate_request(RunRequest("frontier_v3", ("piagent",), (), "test"))


def test_gui_skill_interventions_are_frontier_v4_only():
    service = BenchmarkService(ROOT)
    with pytest.raises(ValueError, match="available only for Frontier v4"):
        service.validate_request(
            RunRequest(
                "frontier_v3",
                ("piagent",),
                ("autonomy_001",),
                "test",
                skill_mode="curated_skill",
            )
        )
    with pytest.raises(ValueError, match="available only for Frontier v4"):
        service.validate_request(
            RunRequest(
                "frontier_v3",
                ("piagent",),
                ("autonomy_001",),
                "test",
                skill_ablation=True,
            )
        )


def test_gui_horizon_profile_is_v4_only_and_owns_task_selection():
    service = BenchmarkService(ROOT)
    profile = get_horizon_profile()
    required = tuple(dict.fromkeys(cell.task_id for cell in profile.cells))

    with pytest.raises(ValueError, match="available only for Frontier v4"):
        service.validate_request(
            RunRequest(
                "frontier_v3",
                ("piagent",),
                ("autonomy_001",),
                "test",
                horizon_profile=profile.id,
            )
        )
    with pytest.raises(ValueError, match="owns task selection"):
        service.validate_request(
            RunRequest(
                "frontier_v4",
                ("piagent",),
                (required[0],),
                "test",
                horizon_profile=profile.id,
            )
        )

    tasks = service.validate_request(
        RunRequest(
            "frontier_v4",
            ("piagent",),
            required,
            "test",
            horizon_profile=profile.id,
        )
    )
    assert {task.id for task in tasks} == set(required)


def test_gui_horizon_run_delegates_to_shared_profile_executor(monkeypatch, tmp_path: Path):
    service = BenchmarkService(ROOT)
    service.results_root = tmp_path / "results"
    profile = get_horizon_profile()
    required = tuple(dict.fromkeys(cell.task_id for cell in profile.cells))
    request = RunRequest(
        "frontier_v4",
        ("piagent",),
        required,
        "test",
        horizon_profile=profile.id,
    )
    events = []
    observed = {}

    def fake_execute(selected_profile, **kwargs):
        observed["profile"] = selected_profile
        observed.update(kwargs)
        return SimpleNamespace(exit_code=0)

    monkeypatch.setattr("core.run_service.execute_horizon_profile", fake_execute)

    result = service.run(request, events.append)

    assert result["exit_code"] == 0
    assert observed["profile"].digest == profile.digest
    assert observed["harnesses"] == ("piagent",)
    assert observed["skill_modes"] == ("no_skill",)
    assert observed["repeats"] == 1
    assert events[-1]["type"] == "run_finished"
    assert events[-1]["total_units"] == 15
