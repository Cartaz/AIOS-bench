from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from core.cancellation import RunCancelled

from .adapters import PiAgentAdapter
from .evaluators import evaluate_artifacts
from .failures import classify_failure
from .goose_telemetry import parse_goose_stream_json
from .hermes_telemetry import parse_hermes_usage_report
from .letta_telemetry import parse_letta_stream_json
from .models import Task, Trajectory
from .pi_rpc import PiRPCClient
from .processes import spawn_owned, terminate_owned
from .sandbox import workspace_sandbox
from .scoring import overall_score
from .server_metrics import NullServerMetricsClient, OutputTokenGuard
from .task_runtime import TaskRuntime
from .telemetry import parse_output


class TaskExecutionRunner(Protocol):
    """Minimal public runner surface required by the task executor."""

    repo_root: Path
    run_dir: Path
    run_id: str
    model: str
    agent: Any
    server_metrics: Any
    max_output_tokens: int
    metrics_poll_interval: float
    cancellation_check: Callable[[], bool] | None

    def prepare_workspace(self, task: Task) -> Path: ...

    def start_task_runtime(self, task: Task, workspace: Path) -> TaskRuntime: ...

    def record_event(self, event: dict) -> None: ...

    def result_identity(self, task: Task) -> dict: ...

    def record_result(self, item: dict) -> None: ...


@dataclass(frozen=True)
class ProcessOutcome:
    returncode: int
    timed_out: bool = False
    runaway: bool = False
    cancelled: bool = False


def _run_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdout: Any,
    stderr: Any,
    timeout: float,
    runaway_check: Callable[[], bool] | None,
    cancellation_check: Callable[[], bool] | None = None,
) -> ProcessOutcome:
    """Run a local harness while polling timeout, token cap and cancellation."""
    proc = spawn_owned(
        command,
        cwd=cwd,
        env=env,
        stdout=stdout,
        stderr=stderr,
        text=True,
    )
    started = time.monotonic()
    timed_out = False
    runaway = False
    cancelled = False
    try:
        while proc.poll() is None:
            if cancellation_check is not None and cancellation_check():
                cancelled = True
                break
            if time.monotonic() - started >= timeout:
                timed_out = True
                break
            if runaway_check is not None and runaway_check():
                runaway = True
                break
            try:
                proc.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass
    finally:
        terminate_owned(proc)
    return ProcessOutcome(
        proc.returncode if proc.returncode is not None else 1,
        timed_out,
        runaway,
        cancelled,
    )


def _usage_source(trajectory: Trajectory, server_usage: dict[str, Any]) -> str:
    if server_usage.get("trusted_for_efficiency"):
        return "server_verified"
    if trajectory.input_tokens > 0 or trajectory.output_tokens > 0:
        return "harness_reported"
    return "unavailable"


def _parse_harness_output(
    stdout: str,
    stderr: str,
    source: str,
    *,
    hermes_usage: str = "",
) -> list[dict[str, Any]]:
    if source == "goose":
        events = parse_goose_stream_json(stdout, source=source)
        events.extend(parse_output("", stderr, source=source))
    elif source == "letta":
        events = parse_letta_stream_json(stdout, source=source)
        events.extend(parse_output("", stderr, source=source))
    elif source == "hermes":
        events = parse_hermes_usage_report(hermes_usage, source=source)
        events.extend(parse_output("", stderr, source=source))
    else:
        events = parse_output(stdout, stderr, source=source)
    return [event.to_dict() for event in events]


def run_frontier_task(
    runner: TaskExecutionRunner,
    task: Task,
    timeout: float,
) -> Trajectory:
    """Execute one Frontier task with optional server-verified telemetry."""
    cancellation_check = runner.cancellation_check
    if cancellation_check is not None and cancellation_check():
        raise RunCancelled("Benchmark run cancelled")

    workspace = runner.prepare_workspace(task)
    logs = runner.run_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout_path = logs / f"{task.id}.stdout.log"
    stderr_path = logs / f"{task.id}.stderr.log"
    prompt = (
        "You are being evaluated by AIOS-bench. Work only inside the provided workspace. "
        "Complete the task fully, verify the result, and do not modify benchmark files outside "
        "the workspace.\n\nTASK:\n" + task.prompt
    )
    invocation = runner.agent.adapter.build(prompt, workspace, runner.model)
    command = invocation.command
    custom = os.environ.get(f"AIOS_BENCH_{runner.agent.name.upper()}_COMMAND")
    if custom:
        command = [*shlex.split(custom), prompt]
    sandbox = workspace_sandbox(runner.agent.name, workspace)
    command = sandbox.wrap(command)
    env = os.environ.copy()
    env.update(invocation.environment)
    env.update({
        "AIOS_BENCH_TASK_ID": task.id,
        "AIOS_BENCH_AGENT": runner.agent.name,
        "AIOS_BENCH_MODEL": runner.model,
        "AIOS_BENCH_RUN_ID": runner.run_id,
        "AIOS_BENCH_FIXTURE_ROOT": str(
            runner.repo_root / "benchmarks" / "fixtures" / "workspace"
        ),
        # Remote harness clients use the same active task budget as the local
        # process owner rather than introducing an unbounded network wait.
        "AIOS_BENCH_TASK_TIMEOUT_SECONDS": str(timeout),
    })

    metrics_client = runner.server_metrics or NullServerMetricsClient()
    metrics_before = metrics_client.snapshot()
    guard = OutputTokenGuard(
        metrics_client,
        metrics_before,
        runner.max_output_tokens,
        poll_interval=runner.metrics_poll_interval,
    )

    runtime = runner.start_task_runtime(task, workspace)
    env.update(runtime.environment)
    runner.record_event({
        "event": "task_started",
        "task_id": task.id,
        "command": command,
        "model": runner.model,
        "tier": task.tier,
        "task_revision": task.revision,
        "server_metrics_available": metrics_before.available,
    })
    started = time.monotonic()
    trajectory = Trajectory(agent=runner.agent.name, task_id=task.id)
    status = "completed"
    try:
        if isinstance(runner.agent.adapter, PiAgentAdapter):
            result = PiRPCClient(
                runner.model,
                workspace,
                timeout,
                environment=env,
                command=command,
                runaway_check=guard.check if guard.enabled else None,
                cancellation_check=cancellation_check,
            ).run(prompt)
            stdout_path.write_text(result.stdout, encoding="utf-8")
            stderr_path.write_text(result.stderr, encoding="utf-8")
            if result.cancelled:
                raise RunCancelled("Benchmark run cancelled")
            if result.runaway:
                status = "runaway"
                trajectory.errors = 1
                trajectory.events.append({
                    "type": "error",
                    "source": "runner",
                    "data": {"kind": "output_token_cap", "limit": guard.limit},
                })
            elif result.timed_out:
                status = "timeout"
                trajectory.errors = 1
                trajectory.events.append({
                    "type": "error",
                    "source": "runner",
                    "data": {"kind": "timeout", "message": "Pi RPC task timeout"},
                })
            else:
                trajectory.success = result.returncode == 0
                if result.returncode != 0:
                    status = "failed"
                    trajectory.errors = 1
        else:
            with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open(
                "w", encoding="utf-8"
            ) as err:
                process = _run_process(
                    command,
                    cwd=workspace,
                    env=env,
                    stdout=out,
                    stderr=err,
                    timeout=timeout,
                    runaway_check=guard.check if guard.enabled else None,
                    cancellation_check=cancellation_check,
                )
            if process.cancelled:
                raise RunCancelled("Benchmark run cancelled")
            if process.runaway:
                status = "runaway"
                trajectory.errors = 1
                trajectory.events.append({
                    "type": "error",
                    "source": "runner",
                    "data": {"kind": "output_token_cap", "limit": guard.limit},
                })
            elif process.timed_out:
                status = "timeout"
                trajectory.errors = 1
                trajectory.events.append({
                    "type": "error",
                    "source": "runner",
                    "data": {"kind": "timeout", "message": "task timeout"},
                })
            else:
                trajectory.success = process.returncode == 0
                if process.returncode != 0:
                    status = "failed"
                    trajectory.errors = 1
    except RunCancelled:
        raise
    except FileNotFoundError as exc:
        status = "error"
        trajectory.errors = 1
        trajectory.events.append({
            "type": "error",
            "source": "runner",
            "data": {"kind": "agent_not_found", "error": str(exc)},
        })
    except Exception as exc:
        status = "error"
        trajectory.errors = 1
        trajectory.events.append({
            "type": "error",
            "source": "runner",
            "data": {"kind": "runner_error", "error": repr(exc)},
        })
    finally:
        runtime.close()
    trajectory.duration_seconds = time.monotonic() - started

    if cancellation_check is not None and cancellation_check():
        raise RunCancelled("Benchmark run cancelled")

    metrics_after = (
        guard.last_snapshot
        if guard.triggered and guard.last_snapshot is not None
        else metrics_client.snapshot()
    )
    server_usage = metrics_client.delta(metrics_before, metrics_after)
    server_usage.update({
        "source": getattr(metrics_client, "source", "unavailable"),
        "endpoint": getattr(metrics_client, "public_endpoint", None),
        "scope": "endpoint_aggregate",
        "requires_exclusive_server": True,
        "output_token_cap": guard.limit,
        "runaway_triggered": bool(guard.triggered),
    })

    stdout = (
        stdout_path.read_text(encoding="utf-8", errors="replace")
        if stdout_path.exists()
        else ""
    )
    stderr = (
        stderr_path.read_text(encoding="utf-8", errors="replace")
        if stderr_path.exists()
        else ""
    )
    hermes_usage = ""
    if runner.agent.name == "hermes":
        usage_value = invocation.environment.get("AIOS_BENCH_HERMES_USAGE_FILE")
        if usage_value:
            usage_path = Path(usage_value)
            try:
                if usage_path.is_file():
                    hermes_usage = usage_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
            finally:
                usage_path.unlink(missing_ok=True)

    runner_events = list(trajectory.events)
    parsed_events = _parse_harness_output(
        stdout,
        stderr,
        runner.agent.name,
        hermes_usage=hermes_usage,
    )
    trajectory.apply_events([*runner_events, *parsed_events])
    if trajectory.errors and status == "completed":
        status = "failed"
        trajectory.success = False
    execution_success = bool(trajectory.success)

    trajectory.events.append({
        "type": "server_metrics",
        "source": "runner",
        "data": server_usage,
    })

    evaluation = None
    evaluation_passed: bool | None = None
    checks = list(task.acceptance)
    spec = runner.repo_root / "benchmarks" / "tasks" / "specs" / f"{task.id}.json"
    if not checks and spec.is_file():
        checks = json.loads(spec.read_text(encoding="utf-8"))["checks"]
    if checks:
        evaluation = evaluate_artifacts(
            workspace,
            checks,
            run_dir=runner.run_dir,
            events=trajectory.events,
            fixture_root=runner.repo_root / "benchmarks" / "fixtures" / "workspace",
        )
        evaluation_passed = bool(evaluation["passed"])
        trajectory.evaluation_score = float(evaluation["acceptance_score"])
        trajectory.success = trajectory.success and evaluation_passed
        if not trajectory.success and status == "completed":
            status = "failed"
        trajectory.events.append({"type": "deterministic_evaluation", "result": evaluation})

    failure_kind = classify_failure(
        status=status,
        success=bool(trajectory.success),
        execution_success=execution_success,
        evaluation_passed=evaluation_passed,
        events=trajectory.events,
    )
    result = trajectory.to_dict()
    result.update({
        "status": status,
        "failure_kind": failure_kind,
        "evaluation": evaluation,
        "score": overall_score(trajectory),
        **runner.result_identity(task),
        "comparable": True,
        "capability_assessment": runner.agent.adapter.assess_task(task).to_dict(),
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "usage_source": _usage_source(trajectory, server_usage),
        "efficiency_comparable": bool(server_usage.get("trusted_for_efficiency")),
        "server_usage": server_usage,
    })
    runner.record_result(result)
    runner.record_event({
        "event": "task_finished",
        "task_id": task.id,
        "success": trajectory.success,
        "status": status,
        "failure_kind": failure_kind,
        "duration": trajectory.duration_seconds,
        "score": result["score"],
        "usage_source": result["usage_source"],
        "telemetry_available": trajectory.telemetry_available,
        "tier": task.tier,
    })
    return trajectory
