import json
from pathlib import Path

from core.benchmark.aios_index import get_aios_index_profile
from core.benchmark.aios_index_execution import execute_aios_index_profile
from core.benchmark.paths import TASKS_ROOT
from core.benchmark.tasks import load_tasks


class FakeRunner:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True)
        self.seen = []

    def run(self, tasks) -> int:
        self.seen = list(tasks)
        (self.run_dir / "run.json").write_text(
            json.dumps({"run_id": self.run_dir.name, "task_count": len(self.seen), "run_status": "completed"}),
            encoding="utf-8",
        )
        (self.run_dir / "results.jsonl").write_text(
            "\n".join(
                json.dumps({"task_id": task.id, "status": "completed", "success": True, "score": 100.0})
                for task in self.seen
            ) + "\n",
            encoding="utf-8",
        )
        return 0

    def abort(self, tasks) -> None:
        return None


def test_aios_index_execution_uses_profile_selection_pressures_and_context(tmp_path: Path) -> None:
    profile = get_aios_index_profile()
    tasks = load_tasks(TASKS_ROOT, "frontier_v4")
    calls = []
    runners = []

    def factory(harness, run_id, seed, parameters):
        calls.append((harness, run_id, seed, parameters))
        runner = FakeRunner(tmp_path / harness / run_id)
        runners.append(runner)
        return runner

    result = execute_aios_index_profile(
        profile,
        tasks=tasks,
        harnesses=("piagent",),
        repeats=1,
        base_seed=42,
        experiment_id="index-exp",
        runner_factory=factory,
    )

    assert result.exit_code == 0
    assert len(result.run_dirs) == 1
    assert [task.id for task in runners[0].seen] == [
        task.id for task in profile.select_tasks(tasks)
    ]
    assert calls[0][2] == 42
    assert calls[0][3] == profile.parameters()
    metadata = json.loads((result.run_dirs[0] / "run.json").read_text(encoding="utf-8"))
    assert metadata["experiment_context"]["kind"] == "aios_index"
    assert metadata["experiment_context"]["profile_digest"] == profile.digest
    assert metadata["schedule_mode"] == "aios_index_sequential"


def test_aios_index_execution_repeat_seeds_are_independent(tmp_path: Path) -> None:
    profile = get_aios_index_profile()
    tasks = load_tasks(TASKS_ROOT, "frontier_v4")
    seeds = []

    def factory(harness, run_id, seed, parameters):
        seeds.append(seed)
        return FakeRunner(tmp_path / f"{harness}-{run_id}")

    result = execute_aios_index_profile(
        profile,
        tasks=tasks,
        harnesses=("piagent",),
        repeats=3,
        base_seed=100,
        experiment_id="index-exp",
        runner_factory=factory,
    )

    assert result.exit_code == 0
    assert seeds == [100, 101, 102]
    assert len(result.run_dirs) == 3
