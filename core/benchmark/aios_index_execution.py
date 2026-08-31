from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .aios_index import AIOSIndexProfile
from .experiments import annotate_experiment
from .models import Task
from .scheduler import MatchedInterleavedScheduler


RunnerFactory = Callable[
    [str, str, int, Mapping[str, Mapping[str, int]]],
    object,
]


@dataclass(frozen=True)
class IndexExecutionResult:
    exit_code: int
    run_dirs: tuple[Path, ...]


def execute_aios_index_profile(
    profile: AIOSIndexProfile,
    *,
    tasks: list[Task],
    harnesses: tuple[str, ...],
    repeats: int,
    base_seed: int,
    experiment_id: str,
    runner_factory: RunnerFactory,
) -> IndexExecutionResult:
    """Execute one compact profile without creating alternate task semantics."""
    if not harnesses:
        raise ValueError("AIOS-Index requires at least one harness")
    if repeats < 1:
        raise ValueError("AIOS-Index repeats must be at least 1")
    selected_tasks = profile.select_tasks(tasks)
    context = profile.context()
    parameters = profile.parameters()
    exit_code = 0
    run_dirs: list[Path] = []

    for repeat in range(1, repeats + 1):
        orchestration_seed = int(base_seed) + repeat - 1
        base_run_id = experiment_id if repeats == 1 else f"{experiment_id}-r{repeat:02d}"
        runners = {
            harness: runner_factory(
                harness,
                base_run_id,
                orchestration_seed,
                parameters,
            )
            for harness in harnesses
        }
        if len(runners) == 1:
            runner = next(iter(runners.values()))
            try:
                exit_code = max(exit_code, runner.run(selected_tasks))
            except BaseException:
                runner.abort(selected_tasks)
                annotate_experiment(
                    runner.run_dir,
                    experiment_id=experiment_id,
                    repeat=repeat,
                    orchestration_seed=orchestration_seed,
                    schedule_mode="aios_index_sequential",
                    context=context,
                )
                raise
            annotate_experiment(
                runner.run_dir,
                experiment_id=experiment_id,
                repeat=repeat,
                orchestration_seed=orchestration_seed,
                schedule_mode="aios_index_sequential",
                context=context,
            )
            run_dirs.append(runner.run_dir)
            continue

        result = MatchedInterleavedScheduler(
            runners,
            selected_tasks,
            experiment_id=experiment_id,
            repeat=repeat,
            orchestration_seed=orchestration_seed,
            experiment_context=context,
        ).run()
        exit_code = max(exit_code, result.exit_code)
        run_dirs.extend(result.run_dirs.values())

    return IndexExecutionResult(exit_code=exit_code, run_dirs=tuple(run_dirs))


__all__ = ["IndexExecutionResult", "execute_aios_index_profile"]
