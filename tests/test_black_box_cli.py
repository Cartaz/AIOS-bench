from __future__ import annotations

from pathlib import Path

import pytest

from aios_bench import cli
from aios_bench.config import AGENTS
from aios_bench.frontier_v4_runner import FrontierV4Runner
from aios_bench.parametric import normalize_parameters
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"
TASK_ID = "software_black_box_001"


def test_black_box_cli_pressure_coordinates_reach_validation(monkeypatch, capsys) -> None:
    observed: dict[str, object] = {}

    def fake_validate(repo_root, tasks, *, base_seed, parameters):
        observed["repo_root"] = repo_root
        observed["task_ids"] = [task.id for task in tasks]
        observed["base_seed"] = base_seed
        observed["parameters"] = parameters
        return {"schema": "test", "ok": True, "failures": []}

    monkeypatch.setattr(cli, "validate_parametric_baseline", fake_validate)
    monkeypatch.setattr(cli, "apply_profile_environment", lambda: {})
    monkeypatch.setattr(
        "sys.argv",
        [
            "aiosbench",
            "--suite",
            "frontier_v4",
            "--seed",
            "73",
            "--v4-black-box-rules",
            "8",
            "--v4-black-box-public-examples",
            "21",
            "--v4-black-box-probe-budget",
            "64",
            "--v4-black-box-distractor-fields",
            "6",
            "--v4-black-box-max-units",
            "900",
            "validate",
        ],
    )

    cli.main()

    parameters = observed["parameters"]
    assert isinstance(parameters, dict)
    assert parameters["black_box_reconstruction"] == {
        "rule_count": 8,
        "public_examples": 21,
        "probe_budget": 64,
        "distractor_fields": 6,
        "max_units": 900,
    }
    assert TASK_ID in observed["task_ids"]
    assert observed["base_seed"] == 73
    assert '"ok": true' in capsys.readouterr().out.lower()


def test_black_box_cli_rejects_invalid_pressure(monkeypatch) -> None:
    monkeypatch.setattr(cli, "apply_profile_environment", lambda: {})
    monkeypatch.setattr(
        "sys.argv",
        [
            "aiosbench",
            "--suite",
            "frontier_v4",
            "--v4-black-box-rules",
            "4",
            "validate",
        ],
    )

    with pytest.raises(SystemExit, match="invalid Frontier v4 black-box reconstruction pressure"):
        cli.main()


def test_black_box_variant_identity_records_effective_pressure(tmp_path: Path) -> None:
    parameters = normalize_parameters({
        "black_box_reconstruction": {
            "rule_count": 8,
            "public_examples": 20,
            "probe_budget": 72,
            "distractor_fields": 5,
            "max_units": 850,
        }
    })
    runner = FrontierV4Runner(
        ROOT,
        AGENTS["piagent"],
        tmp_path / "results",
        task_timeout=1,
        total_timeout=None,
        model="test",
        run_id="black-box-identity",
        variant_base_seed=42,
        parametric_parameters=parameters,
    )
    task = next(task for task in load_tasks(TASK_ROOT, "frontier_v4") if task.id == TASK_ID)

    runner._workspace(task)
    identity = runner._result_identity(task)

    assert identity["variant_family"] == "black_box_reconstruction"
    assert identity["variant_parameters"] == {
        "rule_count": 8,
        "public_examples": 20,
        "probe_budget": 72,
        "distractor_fields": 5,
        "max_units": 850,
    }
    assert identity["variant_digest"]
