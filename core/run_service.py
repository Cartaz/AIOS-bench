from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from core.benchmark.config import AGENTS
from core.benchmark.experiments import make_experiment_id
from core.benchmark.frontier_runner import FrontierRunner
from core.benchmark.frontier_v3_runner import frontier_v3_suite
from core.benchmark.frontier_v4_runner import frontier_v4_suite
from core.benchmark.parametric import ConfigTraversalPressure, ExpensePressure
from core.benchmark.report import write_summary
from core.benchmark.scheduler import MatchedInterleavedScheduler
from core.benchmark.statistics import augment_summary_file
from core.benchmark.tasks import load_tasks

SUITES = ("frontier_v3", "frontier_v4")
EventCallback = Callable[[dict[str, object]], None]


@dataclass(frozen=True)
class RunRequest:
    suite: str
    harnesses: tuple[str, ...]
    task_ids: tuple[str, ...]
    model: str
    repeats: int = 1
    seed: int = 42
    task_timeout: float = 900.0
    total_timeout: float | None = None
    server_metrics_url: str | None = None
    server_metrics_model: str | None = None
    max_output_tokens: int = 65536
    metrics_poll_interval: float = 1.0
    keep_raw: bool = False


class BenchmarkService:
    """Application-facing API for catalog discovery and benchmark execution."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.tasks_root = repo_root / "benchmarks" / "tasks"
        self.results_root = repo_root / "results" / ".local"

    def catalog(self, suite: str = "frontier_v3") -> dict[str, object]:
        tasks = load_tasks(self.tasks_root, suite)
        return {
            "suite": suite,
            "suites": list(SUITES),
            "harnesses": [
                {"id": name, "name": config.display_name}
                for name, config in AGENTS.items()
            ],
            "tasks": [
                {
                    "id": task.id,
                    "category": task.category,
                    "tier": task.tier,
                    "mode": task.mode,
                    "depends_on": list(task.depends_on),
                    "required_capabilities": list(task.required_capabilities),
                }
                for task in tasks
            ],
        }

    def validate_request(self, request: RunRequest) -> list:
        if request.suite not in SUITES:
            raise ValueError(f"Unknown suite: {request.suite}")
        if not request.harnesses:
            raise ValueError("Select at least one harness")
        unknown_harnesses = sorted(set(request.harnesses) - set(AGENTS))
        if unknown_harnesses:
            raise ValueError(f"Unknown harnesses: {', '.join(unknown_harnesses)}")
        if request.repeats < 1:
            raise ValueError("Repeats must be at least 1")
        if request.task_timeout <= 0:
            raise ValueError("Task timeout must be greater than 0")
        if request.total_timeout is not None and request.total_timeout <= 0:
            raise ValueError("Total timeout must be greater than 0")
        if request.max_output_tokens < 0:
            raise ValueError("Max output tokens must be at least 0")
        if request.metrics_poll_interval <= 0:
            raise ValueError("Metrics poll interval must be greater than 0")

        catalog = load_tasks(self.tasks_root, request.suite)
        by_id = {task.id: task for task in catalog}
        if not request.task_ids:
            raise ValueError("Select at least one task")
        unknown_tasks = sorted(set(request.task_ids) - set(by_id))
        if unknown_tasks:
            raise ValueError(f"Unknown tasks: {', '.join(unknown_tasks)}")

        selected = set(request.task_ids)
        for task_id in request.task_ids:
            missing = [dep for dep in by_id[task_id].depends_on if dep not in selected]
            if missing:
                raise ValueError(
                    f"Task {task_id} requires selected dependencies: {', '.join(missing)}"
                )
        return [task for task in catalog if task.id in selected]

    def run(self, request: RunRequest, on_event: EventCallback | None = None) -> dict[str, object]:
        tasks = self.validate_request(request)
        callback = on_event or (lambda event: None)
        total_units = len(tasks) * len(request.harnesses) * request.repeats
        completed_units = 0

        def emit(event: dict[str, object]) -> None:
            nonlocal completed_units
            if event.get("type") == "task_finished":
                completed_units += 1
            callback({**event, "completed_units": completed_units, "total_units": total_units})

        exit_code = 0
        experiment_id = make_experiment_id(request.suite)
        for repeat in range(1, request.repeats + 1):
            orchestration_seed = request.seed + repeat - 1
            run_id = experiment_id if request.repeats == 1 else f"{experiment_id}-r{repeat:02d}"
            runners = {
                name: self._build_runner(request, name, run_id, orchestration_seed, emit)
                for name in request.harnesses
            }
            emit({"type": "repeat_started", "repeat": repeat, "repeats": request.repeats})
            if len(runners) == 1:
                runner = next(iter(runners.values()))
                exit_code = max(exit_code, runner.run(tasks))
            else:
                scheduler = MatchedInterleavedScheduler(
                    runners,
                    tasks,
                    experiment_id=experiment_id,
                    repeat=repeat,
                    orchestration_seed=orchestration_seed,
                )
                exit_code = max(exit_code, scheduler.run().exit_code)
            emit({"type": "repeat_finished", "repeat": repeat, "repeats": request.repeats})

        summary = write_summary(self.results_root)
        augment_summary_file(summary, self.results_root)
        result = {
            "exit_code": exit_code,
            "summary": str(summary),
            "request": asdict(request),
        }
        emit({"type": "run_finished", **result})
        return result

    def _build_runner(
        self,
        request: RunRequest,
        harness: str,
        run_id: str,
        orchestration_seed: int,
        callback: EventCallback,
    ) -> "ObservableFrontierRunner":
        if request.suite == "frontier_v4":
            suite = frontier_v4_suite(
                variant_base_seed=orchestration_seed,
                parametric_parameters={
                    "expense_report": ExpensePressure().to_dict(),
                    "config_traversal": ConfigTraversalPressure().to_dict(),
                },
            )
        else:
            suite = frontier_v3_suite()
        return ObservableFrontierRunner(
            repo_root=self.repo_root,
            agent=AGENTS[harness],
            results_dir=self.results_root,
            task_timeout=request.task_timeout,
            total_timeout=request.total_timeout,
            suite=suite,
            resume=False,
            model=request.model or "unknown",
            keep_raw=request.keep_raw,
            run_id=run_id,
            server_metrics_url=request.server_metrics_url,
            server_metrics_model=request.server_metrics_model,
            max_output_tokens=request.max_output_tokens,
            metrics_poll_interval=request.metrics_poll_interval,
            event_callback=callback,
        )


class _ObservableRunnerMixin:
    def __init__(self, *args, event_callback: EventCallback | None = None, **kwargs) -> None:
        self._event_callback = event_callback or (lambda event: None)
        super().__init__(*args, **kwargs)

    def run_task(self, task, timeout):
        self._event_callback({
            "type": "task_started",
            "harness": self.agent.name,
            "task_id": task.id,
            "category": task.category,
            "tier": task.tier,
        })
        trajectory = super().run_task(task, timeout)
        self._event_callback({
            "type": "task_finished",
            "harness": self.agent.name,
            "task_id": task.id,
            "success": bool(trajectory.success),
            "score": float(trajectory.evaluation_score or 0.0),
            "duration_seconds": float(trajectory.duration_seconds),
        })
        return trajectory

    def _write_noncomparable(self, task, status, reason, assessment=None) -> None:
        super()._write_noncomparable(task, status, reason, assessment)
        self._event_callback({
            "type": "task_finished",
            "harness": self.agent.name,
            "task_id": task.id,
            "status": status,
            "success": False,
            "score": None,
            "duration_seconds": 0.0,
        })


class ObservableFrontierRunner(_ObservableRunnerMixin, FrontierRunner):
    pass
