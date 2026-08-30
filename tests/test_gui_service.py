from pathlib import Path

import pytest

from core.run_service import BenchmarkService, RunRequest

ROOT = Path(__file__).resolve().parents[1]


def test_gui_catalog_uses_canonical_harness_and_task_sources():
    service = BenchmarkService(ROOT)
    catalog = service.catalog("frontier_v3")
    assert [item["id"] for item in catalog["harnesses"]] == [
        "hermes", "piagent", "opencode", "goose", "letta", "agentzero", "claude"
    ]
    task_ids = {item["id"] for item in catalog["tasks"]}
    assert "autonomy_001" in task_ids
    assert "tool_use_003" in task_ids
    assert catalog["skill_modes"] == []


def test_gui_catalog_switches_suite_without_mixing_tasks():
    service = BenchmarkService(ROOT)
    catalog = service.catalog("frontier_v4")
    assert {item["id"] for item in catalog["tasks"]} == {
        "autonomy_expense_001",
        "stateful_support_001",
        "support_dependency_001",
        "data_cross_artifact_001",
        "retrieval_wide_001",
        "tool_use_config_001",
        "tool_use_lineage_001",
        "tool_recovery_001",
    }
    assert catalog["skill_modes"] == ["no_skill", "curated_skill"]


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
