from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping

from core.benchmark.aios_index import AIOS_INDEX_PROFILES, get_aios_index_profile
from core.benchmark.aios_index_execution import execute_aios_index_profile
from core.benchmark.config import AGENTS
from core.benchmark.experiments import make_experiment_id
from core.benchmark.frontier_runner import FrontierRunner
from core.benchmark.horizon import HORIZON_PROFILES, get_horizon_profile
from core.benchmark.horizon_execution import execute_horizon_profile
from core.benchmark.interventions import ExecutionCondition, SKILL_MODES
from core.benchmark.models import Task
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
    max_output_tokens: int = 65536
    metrics_poll_interval: float = 1.0
    keep_raw: bool = False
    skill_mode: str = "no_skill"
    skill_ablation: bool = False
    horizon_profile: str | None = None
    index_profile: str | None = None


@dataclass(frozen=True)
class PreparedRun:
    """Validated run request plus its already-loaded task selection."""

    request: RunRequest
    tasks: tuple[Task, ...]


class BenchmarkService:
    """Application-facing API for catalog discovery and benchmark execution."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.tasks_root = repo_root / "benchmarks" / "tasks"
        self.results_root = repo_root / "results" / ".local"

    def catalog(self, suite: str = "frontier_v3") -> dict[str, object]:
        if suite not in SUITES:
            raise ValueError(f"Unknown suite: {suite}")
        tasks = load_tasks(self.tasks_root, suite)
        horizon_profiles = []
        index_profiles = []
        if suite == "frontier_v4":
            horizon_profiles = [
                {
                    "id": profile.id,
                    "cell_count": len(profile.cells),
                    "task_ids": list(dict.fromkeys(cell.task_id for cell in profile.cells)),
                    "profile_digest": profile.digest,
                }
                for profile in HORIZON_PROFILES.values()
            ]
            index_profiles = [
                {
                    "id": profile.id,
                    "task_count": len(profile.task_ids),
                    "task_ids": list(profile.task_ids),
                    "profile_digest": profile.digest,
                }
                for profile in AIOS_INDEX_PROFILES.values()
            ]
        return {
            "suite": suite,
            "suites": list(SUITES),
            "skill_modes": list(SKILL_MODES) if suite == "frontier_v4" else [],
            "horizon_profiles": horizon_profiles,
            "aios_index_profiles": index_profiles,
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

    @staticmethod
    def _horizon_task_ids(profile_id: str) -> tuple[str, ...]:
        profile = get_horizon_profile(profile_id)
        return tuple(dict.fromkeys(cell.task_id for cell in profile.cells))

    @staticmethod
    def _index_task_ids(profile_id: str) -> tuple[str, ...]:
        return get_aios_index_profile(profile_id).task_ids

    def validate_request(self, request: RunRequest) -> list[Task]:
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
        if not isinstance(request.keep_raw, bool):
            raise ValueError("Keep raw must be a boolean")
        if not isinstance(request.skill_ablation, bool):
            raise ValueError("Skill ablation must be a boolean")
        if not isinstance(request.skill_mode, str) or request.skill_mode not in SKILL_MODES:
            raise ValueError(f"Skill mode must be one of: {', '.join(SKILL_MODES)}")
        if request.suite != "frontier_v4" and (
            request.skill_ablation or request.skill_mode != "no_skill"
        ):
            raise ValueError("Skill interventions are available only for Frontier v4")
        if request.horizon_profile is not None and not isinstance(request.horizon_profile, str):
            raise ValueError("Long-horizon profile must be a string or null")
        if request.index_profile is not None and not isinstance(request.index_profile, str):
            raise ValueError("AIOS-Index profile must be a string or null")
        if request.horizon_profile is not None and request.index_profile is not None:
            raise ValueError("Long-horizon and AIOS-Index profiles are mutually exclusive")

        if request.horizon_profile is not None:
            if request.suite != "frontier_v4":
                raise ValueError("Long-horizon profiles are available only for Frontier v4")
            try:
                required_horizon_tasks = self._horizon_task_ids(request.horizon_profile)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
        else:
            required_horizon_tasks = ()

        if request.index_profile is not None:
            if request.suite != "frontier_v4":
                raise ValueError("AIOS-Index profiles are available only for Frontier v4")
            if request.skill_ablation or request.skill_mode != "no_skill":
                raise ValueError("AIOS-Index uses the canonical no-skill condition")
            try:
                required_index_tasks = self._index_task_ids(request.index_profile)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
        else:
            required_index_tasks = ()

        if not isinstance(request.model, str):
            raise ValueError("Model must be a string")
        for value, label in (
            (request.server_metrics_url, "Server metrics URL"),
            (request.server_metrics_model, "Server metrics model"),
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
        if required_horizon_tasks and set(request.task_ids) != set(required_horizon_tasks):
            raise ValueError(
                "Long-horizon profile owns task selection; required tasks: "
                + ", ".join(required_horizon_tasks)
            )
        if required_index_tasks and set(request.task_ids) != set(required_index_tasks):
            raise ValueError(
                "AIOS-Index profile owns task selection; required tasks: "
                + ", ".join(required_index_tasks)
            )

        selected = set(request.task_ids)
        for task_id in request.task_ids:
            missing = [dep for dep in by_id[task_id].depends_on if dep not in selected]
            if missing:
                raise ValueError(
                    f"Task {task_id} requires selected dependencies: {', '.join(missing)}"
                )
        return [task for task in catalog if task.id in selected]

    def prepare(self, request: RunRequest) -> PreparedRun:
        return PreparedRun(request=request, tasks=tuple(self.validate_request(request)))

    @staticmethod
    def _abort_runners(runners: dict[str, "ObservableFrontierRunner"], tasks: list[Task]) -> None:
        """Best-effort cleanup that never prevents another runner from being aborted."""
        for name, runner in runners.items():
            try:
                runner.abort(tasks)
            except Exception:
                logger.exception("Failed to abort benchmark runner %s", name)

    @staticmethod
    def _conditions(request: RunRequest) -> tuple[str, ...]:
        return SKILL_MODES if request.skill_ablation else (request.skill_mode,)

    def run(
        self,
        request: RunRequest | PreparedRun,
        on_event: EventCallback | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> dict[str, object]:
        prepared = request if isinstance(request, PreparedRun) else self.prepare(request)
        run_request = prepared.request
        tasks = list(prepared.tasks)
        callback = on_event or (lambda event: None)
        token = cancellation_token or CancellationToken()
        conditions = self._conditions(run_request)
        horizon = (
            get_horizon_profile(run_request.horizon_profile)
            if run_request.horizon_profile is not None
            else None
        )
        index = (
            get_aios_index_profile(run_request.index_profile)
            if run_request.index_profile is not None
            else None
        )
        work_items = len(horizon.cells) if horizon is not None else len(tasks)
        total_units = (
            work_items
            * len(run_request.harnesses)
            * len(conditions)
            * run_request.repeats
        )
        completed_units = 0
        active_runners: dict[str, ObservableFrontierRunner] = {}

        def emit(event: dict[str, object]) -> None:
            nonlocal completed_units
            if event.get("type") == "task_finished":
                completed_units += 1
            callback({**event, "completed_units": completed_units, "total_units": total_units})

        exit_code = 0
        experiment_id = make_experiment_id(run_request.suite)
        if horizon is not None:
            experiment_id += "-horizon"
        elif index is not None:
            experiment_id += "-aios-index"
        try:
            if horizon is not None:
                by_id = {task.id: task for task in tasks}

                def horizon_runner_factory(
                    harness: str,
                    run_id: str,
                    orchestration_seed: int,
                    skill_mode: str,
                    parameters: Mapping[str, Mapping[str, int]],
                ) -> ObservableFrontierRunner:
                    return self._build_runner(
                        run_request,
                        harness,
                        run_id,
                        orchestration_seed,
                        emit,
                        token,
                        skill_mode=skill_mode,
                        parametric_parameters=parameters,
                    )

                exit_code = execute_horizon_profile(
                    horizon,
                    tasks=by_id,
                    harnesses=run_request.harnesses,
                    skill_modes=conditions,
                    repeats=run_request.repeats,
                    base_seed=run_request.seed,
                    experiment_id=experiment_id,
                    runner_factory=horizon_runner_factory,
                ).exit_code
                token.raise_if_cancelled()
            elif index is not None:

                def index_runner_factory(
                    harness: str,
                    run_id: str,
                    orchestration_seed: int,
                    parameters: Mapping[str, Mapping[str, int]],
                ) -> ObservableFrontierRunner:
                    return self._build_runner(
                        run_request,
                        harness,
                        run_id,
                        orchestration_seed,
                        emit,
                        token,
                        skill_mode="no_skill",
                        parametric_parameters=parameters,
                    )

                exit_code = execute_aios_index_profile(
                    index,
                    tasks=tasks,
                    harnesses=run_request.harnesses,
                    repeats=run_request.repeats,
                    base_seed=run_request.seed,
                    experiment_id=experiment_id,
                    runner_factory=index_runner_factory,
                ).exit_code
                token.raise_if_cancelled()
            else:
                for repeat in range(1, run_request.repeats + 1):
                    token.raise_if_cancelled()
                    orchestration_seed = run_request.seed + repeat - 1
                    active_runners = {}
                    for harness in run_request.harnesses:
                        for skill_mode in conditions:
                            logical_name = (
                                harness
                                if len(conditions) == 1
                                else f"{harness}:{skill_mode}"
                            )
                            if len(conditions) == 1:
                                run_id = (
                                    experiment_id
                                    if run_request.repeats == 1
                                    else f"{experiment_id}-r{repeat:02d}"
                                )
                            else:
                                arm = skill_mode.replace("_", "-")
                                run_id = f"{experiment_id}-{arm}"
                                if run_request.repeats > 1:
                                    run_id += f"-r{repeat:02d}"
                            active_runners[logical_name] = self._build_runner(
                                run_request,
                                harness,
                                run_id,
                                orchestration_seed,
                                emit,
                                token,
                                skill_mode=skill_mode,
                            )
                    emit({"type": "repeat_started", "repeat": repeat, "repeats": run_request.repeats})
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
                    emit({"type": "repeat_finished", "repeat": repeat, "repeats": run_request.repeats})
        except RunCancelled:
            self._abort_runners(active_runners, tasks)
            result = {
                "exit_code": 2,
                "cancelled": True,
                "summary": None,
                "request": asdict(run_request),
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
            "request": asdict(run_request),
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
        *,
        skill_mode: str = "no_skill",
        parametric_parameters: Mapping[str, Mapping[str, int]] | None = None,
    ) -> "ObservableFrontierRunner":
        if request.suite == "frontier_v4":
            suite = frontier_v4_suite(
                variant_base_seed=orchestration_seed,
                parametric_parameters=parametric_parameters,
            )
            execution_condition = ExecutionCondition(skill_mode=skill_mode)
        else:
            suite = frontier_v3_suite()
            execution_condition = None
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
            cancellation_check=(
                (lambda: cancellation_token.is_cancelled)
                if cancellation_token is not None
                else None
            ),
            execution_condition=execution_condition,
            event_callback=callback,
        )


class _ObservableRunnerMixin:
    def __init__(self, *args, event_callback: EventCallback | None = None, **kwargs) -> None:
        self._event_callback = event_callback or (lambda event: None)
        super().__init__(*args, **kwargs)

    def _condition_event(self) -> dict[str, object]:
        condition = getattr(self, "execution_condition", None)
        skill_mode = getattr(condition, "skill_mode", None)
        return {"skill_mode": skill_mode} if skill_mode else {}

    def run_task(self, task, timeout):
        self._event_callback({
            "type": "task_started",
            "harness": self.agent.name,
            "task_id": task.id,
            "category": task.category,
            "tier": task.tier,
            **self._condition_event(),
        })
        trajectory = super().run_task(task, timeout)
        self._event_callback({
            "type": "task_finished",
            "harness": self.agent.name,
            "task_id": task.id,
            "success": bool(trajectory.success),
            "score": float(trajectory.evaluation_score or 0.0),
            "duration_seconds": float(trajectory.duration_seconds),
            **self._condition_event(),
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
            **self._condition_event(),
        })


class ObservableFrontierRunner(_ObservableRunnerMixin, FrontierRunner):
    pass
