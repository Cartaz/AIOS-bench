from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .experiments import TaskBlock, annotate_experiment, matched_schedule
from .models import Task

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _task_outcome_text(runner: Any, task: Task, success: bool) -> tuple[str, str]:
    """Return the persisted failure taxonomy and score shown to the operator."""
    item = runner.latest_results().get(task.id, {})
    label = "PASS" if success else str(item.get("failure_kind") or "FAIL")
    score = item.get("score")
    return label, f"{float(score):.1f}/100" if score is not None else "n/a"


@dataclass(frozen=True)
class InterleavedResult:
    exit_code: int
    run_dirs: dict[str, Path]
    blocks: tuple[TaskBlock, ...]


class MatchedInterleavedScheduler:
    """Execute task × harness blocks while preserving one stateful runner per harness."""

    def __init__(
        self,
        runners: dict[str, Any],
        tasks: list[Task],
        *,
        experiment_id: str,
        repeat: int,
        orchestration_seed: int,
        experiment_context: Mapping[str, Any] | None = None,
    ) -> None:
        if len(runners) < 2:
            raise ValueError("matched interleaving requires at least two harnesses")
        self.runners = runners
        self.tasks = tasks
        self.experiment_id = experiment_id
        self.repeat = int(repeat)
        self.orchestration_seed = int(orchestration_seed)
        self.experiment_context = dict(experiment_context) if experiment_context is not None else None
        self.blocks = tuple(matched_schedule((task.id for task in tasks), runners, orchestration_seed))
        self._block_map = {block.task_id: block for block in self.blocks}

    def _annotate(self, runner: Any) -> None:
        annotate_experiment(
            runner.run_dir,
            experiment_id=self.experiment_id,
            repeat=self.repeat,
            orchestration_seed=self.orchestration_seed,
            schedule_mode="matched_interleaved",
            task_blocks=self._block_map,
            context=self.experiment_context,
        )

    def _finalize(self, aborted: set[str]) -> int:
        exit_code = 0
        for name, runner in self.runners.items():
            status = "aborted" if name in aborted else "completed"
            final = runner.finalize(self.tasks, status=status, finished_at=_utc_now())
            counts = final["counts"]
            cleanup = final["cleanup"]
            self._annotate(runner)
            if status == "aborted":
                exit_code = max(exit_code, 2)
            elif counts["passed_task_count"] != counts["supported_task_count"]:
                exit_code = max(exit_code, 1)
            comparable = [
                item for item in final["latest"].values()
                if item.get("status") != "unsupported" and item.get("score") is not None
            ]
            average = (
                sum(float(item["score"]) for item in comparable) / len(comparable)
                if comparable else 0.0
            )
            print(
                f"\n{name}: {counts['passed_task_count']}/{counts['supported_task_count']} supported tasks passed"
                f" | unsupported={counts['unsupported_task_count']} | average score {average:.1f}/100"
            )
            if not runner.keep_raw:
                print(
                    f"Retention cleanup: removed {cleanup['files_removed']} files and "
                    f"{cleanup['dirs_removed']} dependency/cache directories"
                )
            print(f"Results: {runner.run_dir}")
        return exit_code

    def abort_all(self) -> None:
        """Attempt every runner cleanup even when an earlier cleanup fails."""
        for name, runner in self.runners.items():
            try:
                runner.abort(self.tasks)
            except Exception:
                logger.exception("Failed to abort interleaved runner %s", name)
            try:
                self._annotate(runner)
            except Exception:
                logger.exception("Failed to annotate aborted interleaved runner %s", name)

    def run(self) -> InterleavedResult:
        remaining_budget: dict[str, float | None] = {
            name: runner.total_timeout for name, runner in self.runners.items()
        }
        aborted: set[str] = set()
        by_id = {task.id: task for task in self.tasks}

        print(
            f"Matched interleaved experiment={self.experiment_id} repeat={self.repeat} "
            f"orchestration_seed={self.orchestration_seed}"
        )
        try:
            for runner in self.runners.values():
                self._annotate(runner)
            for block in self.blocks:
                task = by_id[block.task_id]
                print(
                    f"\n--- Block {block.index}/{len(self.blocks)} | {task.id} [T{task.tier}] "
                    f"| task_seed={block.task_seed} ---"
                )
                for position, name in enumerate(block.harness_order, 1):
                    if name in aborted:
                        continue
                    runner = self.runners[name]
                    if task.id in runner.completed([task]):
                        print(f"[{position}/{len(block.harness_order)}] {name}: RESUMED")
                        continue
                    assessment = runner.agent.adapter.assess_task(task)
                    if not assessment.is_supported:
                        runner.record_unsupported(task, assessment)
                        print(
                            f"[{position}/{len(block.harness_order)}] {name}: UNSUPPORTED "
                            f"({', '.join(sorted(assessment.missing))})"
                        )
                        continue
                    latest = runner.latest_results()
                    missing_dependencies = [
                        dependency for dependency in task.depends_on
                        if not latest.get(dependency, {}).get("success", False)
                    ]
                    if missing_dependencies:
                        runner.record_noncomparable(
                            task,
                            "blocked",
                            {"missing_dependencies": missing_dependencies},
                            assessment,
                        )
                        print(
                            f"[{position}/{len(block.harness_order)}] {name}: BLOCKED "
                            f"({', '.join(missing_dependencies)})"
                        )
                        continue

                    budget = remaining_budget[name]
                    timeout = runner.task_timeout if budget is None else min(runner.task_timeout, budget)
                    if timeout <= 0:
                        aborted.add(name)
                        print(f"[{position}/{len(block.harness_order)}] {name}: TOTAL TIMEOUT")
                        continue
                    print(f"[{position}/{len(block.harness_order)}] {name} ...", flush=True)
                    trajectory = runner.run_task(task, timeout)
                    if budget is not None:
                        remaining_budget[name] = max(0.0, budget - trajectory.duration_seconds)
                    label, score_text = _task_outcome_text(
                        runner,
                        task,
                        bool(trajectory.success),
                    )
                    print(
                        f"    {label}  {score_text}  {trajectory.duration_seconds:.1f}s",
                        flush=True,
                    )
        except BaseException:
            self.abort_all()
            raise

        exit_code = self._finalize(aborted)
        return InterleavedResult(
            exit_code=exit_code,
            run_dirs={name: runner.run_dir for name, runner in self.runners.items()},
            blocks=self.blocks,
        )
