from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from core.benchmark.config import AGENTS
from core.benchmark.experiments import make_experiment_id
from core.benchmark.frontier_runner import FrontierRunner
from core.benchmark.parametric import ConfigTraversalPressure, ExpensePressure
from core.benchmark.report import write_summary
from core.benchmark.scheduler import MatchedInterleavedScheduler
from core.benchmark.statistics import augment_summary_file
from core.benchmark.suites import SUITE_NAMES, frontier_v3_suite, frontier_v4_suite
from core.benchmark.tasks import load_tasks
from core.cancellation import CancellationToken, RunCancelled

SUITES = SUITE_NAMES
EventCallback = Callable[[dict[str, object]], None]
logger = logging.getLogger(__name__)


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
    server_resource_url: str | None = None
    max_output_tokens: int = 65536
    metrics_poll_interval: float = 1.0
    resource_poll_interval: float = 1.0
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

    @staticmethod
    def _require_int(value: object, label: str, *, minimum: int | None = None) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} must be an integer")
        if minimum is not None and value < minimum:
            raise ValueError(f"{label} must be at least {minimum}")
        return value

    @staticmethod
    def _require_positive_number(value: object, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} must be a number")
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise ValueError(f"{label} must be greater than 0")
        return number

    def validate_request(self, request: RunRequest) -> list:
        if not isinstance(request.suite, str) or request.suite not in SUITES:
            raise ValueError(f"Unknown suite: {request.suite}")
        if not request.harnesses:
            raise ValueError("Select at least one harness")
        if not all(isinstance(name, str) and name for name in request.harnesses):
            raise ValueError("Harness ids must be non-empty strings")
        unknown_harnesses = sorted(set(request.harnesses) - set(AGENTS))
        if unknown_harnesses:
            raise ValueError(f"Unknown harnesses: {', '.join(unknown_harnesses)}")

        self._require_int(request.repeats, "Repeats", minimum=1)
        self._require_int(request.seed, "Seed")
        self._require_positive_number(request.task_timeout, "Task timeout")
        if request.total_timeout is not None:
            self._require_positive_number(request.total_timeout, "Total timeout")
        self._require_int(request.max_output_tokens, "Max output tokens", minimum=0)
        self._require_positive_number(request.metrics_poll_interval, "Metrics poll interval")
        self._require_positive_number(request.resource_poll_interval, "Resource poll interval")
        if not isinstance(request.keep_raw, bool):
            raise ValueError("Keep raw must be a boolean")
        if not isinstance(request.model, str):
            raise ValueError("Model must be a string")
        for value, label in (
            (request.server_metrics_url, "Server metrics URL"),
            (request.server_metrics_model, "Server metrics model"),
            (request.server_resource_url, "Server resource URL"),
        ):
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{label} must be a string or null")

        catalog = load_tasks(self.tasks_root, request.suite)
        by_id = {task.id: task for task in catalog}
        if not request.task_ids:
            raise ValueError("Select at least one task")
        if not all(isinstance(task_id, str) and task_id for task_id in request.task_ids):
            raise ValueError("Task ids must be non-empty strings")
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

    @staticmethod
    def _abort_runners(runners: dict[str, "ObservableFrontierRunner"], tasks: list) -> None:
        """Best-effort cleanup that never prevents another runner from being aborted."""
        for name, runner in runners.items():
            try:
                runner.abort(tasks)
            except Exception:
                logger.exception("Failed to abort benchmark runner %s", name)

    def run(
        self,
        request: RunRequest,
        on_event: EventCallback | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> dict[str, object]:
        tasks = self.validate_request(request)
        callback = on_event or (lambda event: None)
        token = cancellation_token or CancellationToken()
        total_units = len(tasks) * len(request.harnesses) * request.repeats
        completed_units = 0
        active_runners: dict[str, ObservableFrontierRunner] = {}

        def emit(event: dict[str, object]) -> None:
            nonlocal completed_units
            if event.get("type") == "task_finished":
                completed_units += 1
            callback({**event, "completed_units": completed_units, "total_units": total_units})

        exit_code = 0
        experiment_id = make_experiment_id(request.suite)
        try:
            for repeat in range(1, request.repeats + 1):
                token.raise_if_cancelled()
                orchestration_seed = request.seed + repeat - 1
                run_id = experiment_id if request.repeats == 1 else f"{experiment_id}-r{repeat:02d}"
                active_runners = {
                    name: self._build_runner(
                        request,
                        name,
                        run_id,
                        orchestration_seed,
                        emit,
                        token,
                    )
                    for name in request.harnesses
                }
                emit({"type": "repeat_started", "repeat": repeat, "repeats": request.repeats})
                if len(active_runners) == 1:
                    runner = next(iter(active_runners.values()))
                    exit_code = max(exit_code, runner.run(tasks))
                else:
                    scheduler = MatchedInterleavedScheduler(
                        active_runners,
                        tasks,
                        experiment_id=experiment_id,
                        repeat=repeat,
                        orchestration_seed=orchestration_seed,
                    )
                    exit_code = max(exit_code, scheduler.run().exit_code)
                token.raise_if_cancelled()
                emit({"type": "repeat_finished", "repeat": repeat, "repeats": request.repeats})
        except RunCancelled:
            self._abort_runners(active_runners, tasks)
            result = {
                "exit_code": 2,
                "cancelled": True,
                "summary": None,
                "request": asdict(request),
            }
            emit({"type": "run_cancelled", **result})
            return result
        except BaseException:
            self._abort_runners(active_runners, tasks)
            raise

        summary = write_summary(self.results_root)
        augment_summary_file(summary, self.results_root)
        result = {
            "exit_code": exit_code,
            "cancelled": False,
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
        cancellation_token: CancellationToken | None = None,
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
            server_resource_url=request.server_resource_url,
            max_output_tokens=request.max_output_tokens,
            metrics_poll_interval=request.metrics_poll_interval,
            resource_poll_interval=request.resource_poll_interval,
            cancellation_check=(
                (lambda: cancellation_token.is_cancelled)
                if cancellation_token is not None
                else None
            ),
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
