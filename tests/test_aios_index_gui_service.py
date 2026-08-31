from pathlib import Path
from types import SimpleNamespace

import pytest

from core.benchmark.aios_index import get_aios_index_profile
from core.run_service import BenchmarkService, RunRequest

ROOT = Path(__file__).resolve().parents[1]


def test_gui_catalog_advertises_aios_index_profile_only_for_v4() -> None:
    service = BenchmarkService(ROOT)
    assert service.catalog("frontier_v3")["aios_index_profiles"] == []

    catalog = service.catalog("frontier_v4")
    assert len(catalog["aios_index_profiles"]) == 1
    item = catalog["aios_index_profiles"][0]
    profile = get_aios_index_profile()
    assert item["id"] == profile.id
    assert item["task_count"] == 7
    assert item["task_ids"] == list(profile.task_ids)
    assert item["profile_digest"] == profile.digest


def test_gui_aios_index_is_v4_only_and_owns_task_selection() -> None:
    service = BenchmarkService(ROOT)
    profile = get_aios_index_profile()

    with pytest.raises(ValueError, match="available only for Frontier v4"):
        service.validate_request(
            RunRequest(
                "frontier_v3",
                ("piagent",),
                ("autonomy_001",),
                "test",
                index_profile=profile.id,
            )
        )
    with pytest.raises(ValueError, match="owns task selection"):
        service.validate_request(
            RunRequest(
                "frontier_v4",
                ("piagent",),
                (profile.task_ids[0],),
                "test",
                index_profile=profile.id,
            )
        )

    tasks = service.validate_request(
        RunRequest(
            "frontier_v4",
            ("piagent",),
            profile.task_ids,
            "test",
            index_profile=profile.id,
        )
    )
    assert {task.id for task in tasks} == set(profile.task_ids)


def test_gui_aios_index_rejects_horizon_and_skill_interventions() -> None:
    service = BenchmarkService(ROOT)
    profile = get_aios_index_profile()
    base = dict(
        suite="frontier_v4",
        harnesses=("piagent",),
        task_ids=profile.task_ids,
        model="test",
        index_profile=profile.id,
    )

    with pytest.raises(ValueError, match="mutually exclusive"):
        service.validate_request(RunRequest(**base, horizon_profile="frontier_v4_horizon_v1"))
    with pytest.raises(ValueError, match="canonical no-skill"):
        service.validate_request(RunRequest(**base, skill_mode="curated_skill"))
    with pytest.raises(ValueError, match="canonical no-skill"):
        service.validate_request(RunRequest(**base, skill_ablation=True))


def test_gui_aios_index_delegates_to_shared_executor(monkeypatch, tmp_path: Path) -> None:
    service = BenchmarkService(ROOT)
    service.results_root = tmp_path / "results"
    profile = get_aios_index_profile()
    request = RunRequest(
        "frontier_v4",
        ("piagent",),
        profile.task_ids,
        "test",
        index_profile=profile.id,
    )
    events = []
    observed = {}

    def fake_execute(selected_profile, **kwargs):
        observed["profile"] = selected_profile
        observed.update(kwargs)
        return SimpleNamespace(exit_code=0)

    monkeypatch.setattr("core.run_service.execute_aios_index_profile", fake_execute)

    result = service.run(request, events.append)

    assert result["exit_code"] == 0
    assert observed["profile"].digest == profile.digest
    assert observed["harnesses"] == ("piagent",)
    assert observed["repeats"] == 1
    assert observed["base_seed"] == 42
    assert events[-1]["type"] == "run_finished"
    assert events[-1]["total_units"] == len(profile.task_ids)
