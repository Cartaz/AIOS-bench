from __future__ import annotations

import json
from pathlib import Path

from aios_bench.horizon import HorizonProfile, get_horizon_profile
from aios_bench.horizon_execution import execute_horizon_profile
from aios_bench.models import Task


class _FakeRunner:
    def __init__(
        self,
        run_dir: Path,
        *,
        family: str,
        family_parameters: dict[str, int],
    ) -> None:
        self.run_dir = run_dir
        self.family = family
        self.family_parameters = family_parameters

    def run(self, tasks: list[Task]) -> int:
        task = tasks[0]
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "run.json").write_text(
            json.dumps(
                {
                    "run_id": self.run_dir.name,
                    "manifest": {
                        "model": {
                            "identity_fingerprint": "model-fp",
                            "strictly_comparable": True,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.run_dir / "results.jsonl").write_text(
            json.dumps(
                {
                    "task_id": task.id,
                    "variant_family": self.family,
                    "variant_parameters": self.family_parameters,
                    "variant_digest": f"digest-{self.run_dir.name}",
                    "score": 100,
                    "success": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return 0

    def abort(self, tasks: list[Task]) -> None:
        return


def test_single_harness_horizon_holds_task_seed_constant_across_pressure_cells(
    tmp_path: Path,
) -> None:
    default = get_horizon_profile()
    cells = default.family_cells("stateful_world")[:2]
    profile = HorizonProfile("test-horizon", cells)
    task = Task(
        id="stateful_support_001",
        category="autonomy",
        prompt="test",
    )
    created: list[_FakeRunner] = []

    def factory(
        harness: str,
        run_id: str,
        orchestration_seed: int,
        skill_mode: str,
        parameters: dict[str, dict[str, int]],
    ) -> _FakeRunner:
        assert harness == "piagent"
        assert orchestration_seed == 42
        assert skill_mode == "no_skill"
        runner = _FakeRunner(
            tmp_path / run_id,
            family="stateful_world",
            family_parameters=parameters["stateful_world"],
        )
        created.append(runner)
        return runner

    result = execute_horizon_profile(
        profile,
        tasks={task.id: task},
        harnesses=("piagent",),
        skill_modes=("no_skill",),
        repeats=1,
        base_seed=42,
        experiment_id="exp-horizon",
        runner_factory=factory,
    )

    assert result.exit_code == 0
    assert result.executed_cells == 2
    assert len(created) == 2
    rows = [
        json.loads((runner.run_dir / "results.jsonl").read_text(encoding="utf-8"))
        for runner in created
    ]
    assert rows[0]["task_seed"] == rows[1]["task_seed"]
    assert rows[0]["variant_parameters"] == dict(cells[0].parameters)
    assert rows[1]["variant_parameters"] == dict(cells[1].parameters)
    assert rows[0]["variant_parameters"] != rows[1]["variant_parameters"]
    assert rows[0]["experiment_id"] == rows[1]["experiment_id"] == "exp-horizon"
    assert rows[0]["schedule_mode"] == rows[1]["schedule_mode"] == "pressure_sweep_sequential"
    assert rows[0]["experiment_context"]["profile_digest"] == profile.digest
    assert rows[1]["experiment_context"]["profile_digest"] == profile.digest
    assert [
        rows[0]["experiment_context"]["path_index"],
        rows[1]["experiment_context"]["path_index"],
    ] == [1, 2]
