from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .experiments import annotate_experiment, matched_schedule
from .horizon import HorizonCell, HorizonProfile
from .models import Task
from .scheduler import MatchedInterleavedScheduler


RunnerFactory = Callable[[str, str, int, str, Mapping[str, Mapping[str, int]]], Any]


@dataclass(frozen=True)
class HorizonRunResult:
    exit_code: int
    experiment_id: str
    run_dirs: tuple[Path, ...]
    executed_cells: int


def _cell_run_id(
    experiment_id: str,
    cell: HorizonCell,
    *,
    repeat: int,
    repeats: int,
    skill_mode: str | None = None,
) -> str:
    value = f"{experiment_id}-c{cell.index:02d}-{cell.id}"
    if repeats > 1:
        value += f"-r{repeat:02d}"
    if skill_mode is not None:
        value += f"-{skill_mode.replace('_', '-')}"
    return value


def _run_single_cell(
    *,
    runner: Any,
    task: Task,
    logical_name: str,
    experiment_id: str,
    repeat: int,
    orchestration_seed: int,
    context: Mapping[str, Any],
) -> int:
    block = matched_schedule([task.id], [logical_name], orchestration_seed)[0]
    block_map = {task.id: block}
    try:
        exit_code = runner.run([task])
    except BaseException:
        runner.abort([task])
        annotate_experiment(
            runner.run_dir,
            experiment_id=experiment_id,
            repeat=repeat,
            orchestration_seed=orchestration_seed,
            schedule_mode="pressure_sweep_sequential",
            task_blocks=block_map,
            context=context,
        )
        raise
    annotate_experiment(
        runner.run_dir,
        experiment_id=experiment_id,
        repeat=repeat,
        orchestration_seed=orchestration_seed,
        schedule_mode="pressure_sweep_sequential",
        task_blocks=block_map,
        context=context,
    )
    return int(exit_code)


def execute_horizon_profile(
    profile: HorizonProfile,
    *,
    tasks: Mapping[str, Task],
    harnesses: tuple[str, ...],
    skill_modes: tuple[str, ...],
    repeats: int,
    base_seed: int,
    experiment_id: str,
    runner_factory: RunnerFactory,
) -> HorizonRunResult:
    """Execute one benchmark-owned pressure path through existing runners.

    Every cell reuses the normal Frontier task, materializer, runtime and grader.
    Cells for the same task/repeat deliberately share the orchestration/task seed;
    only their exact pressure vector changes. This controls generated randomness
    without treating path position as a scalar difficulty label.
    """
    if not harnesses:
        raise ValueError("long-horizon execution requires at least one harness")
    if not skill_modes:
        raise ValueError("long-horizon execution requires at least one skill mode")
    if repeats < 1:
        raise ValueError("long-horizon repeats must be positive")

    missing = sorted({cell.task_id for cell in profile.cells} - set(tasks))
    if missing:
        raise ValueError(f"long-horizon profile references unknown tasks: {', '.join(missing)}")

    exit_code = 0
    run_dirs: list[Path] = []
    for repeat in range(1, repeats + 1):
        orchestration_seed = int(base_seed) + repeat - 1
        for cell in profile.cells:
            task = tasks[cell.task_id]
            parameters = profile.parameters_for(cell)
            context = profile.context_for(cell)
            runners: dict[str, Any] = {}
            for harness in harnesses:
                for skill_mode in skill_modes:
                    logical_name = (
                        harness
                        if len(skill_modes) == 1
                        else f"{harness}:{skill_mode}"
                    )
                    arm = skill_mode if len(skill_modes) > 1 else None
                    run_id = _cell_run_id(
                        experiment_id,
                        cell,
                        repeat=repeat,
                        repeats=repeats,
                        skill_mode=arm,
                    )
                    runners[logical_name] = runner_factory(
                        harness,
                        run_id,
                        orchestration_seed,
                        skill_mode,
                        parameters,
                    )

            print(
                f"\n=== long-horizon {profile.id} | cell {cell.index}/{len(profile.cells)} "
                f"| {cell.family} p{cell.path_index} | seed={orchestration_seed} ==="
            )
            if len(runners) == 1:
                logical_name, runner = next(iter(runners.items()))
                exit_code = max(
                    exit_code,
                    _run_single_cell(
                        runner=runner,
                        task=task,
                        logical_name=logical_name,
                        experiment_id=experiment_id,
                        repeat=repeat,
                        orchestration_seed=orchestration_seed,
                        context=context,
                    ),
                )
                run_dirs.append(runner.run_dir)
            else:
                scheduler = MatchedInterleavedScheduler(
                    runners,
                    [task],
                    experiment_id=experiment_id,
                    repeat=repeat,
                    orchestration_seed=orchestration_seed,
                    experiment_context=context,
                )
                result = scheduler.run()
                exit_code = max(exit_code, result.exit_code)
                run_dirs.extend(result.run_dirs.values())

    return HorizonRunResult(
        exit_code=exit_code,
        experiment_id=experiment_id,
        run_dirs=tuple(run_dirs),
        executed_cells=len(profile.cells) * repeats,
    )


__all__ = ["HorizonRunResult", "RunnerFactory", "execute_horizon_profile"]
