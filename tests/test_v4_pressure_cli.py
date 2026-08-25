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
