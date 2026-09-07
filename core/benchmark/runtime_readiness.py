from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from core.cancellation import RunCancelled

from .adapters import PiAgentAdapter
from .harness_process import prepare_harness_process
from .pi_rpc import PiRPCClient
from .processes import run_owned


RUNTIME_PROBE_TASK_ID = "_runtime_probe"
RUNTIME_PROBE_TIMEOUT_SECONDS = 120.0
RUNTIME_PROBE_MARKER = "AIOS_BENCH_READY"
CLAUDE_BASH_PROBE_MARKER = "AIOS_BENCH_BASH_READY"
RUNTIME_PROBE_PROMPT = (
    "AIOS-Bench runtime readiness probe. Do not use tools or modify files. "
    f"Reply exactly: {RUNTIME_PROBE_MARKER}"
)
CLAUDE_RUNTIME_PROBE_PROMPT = (
    "AIOS-Bench runtime readiness probe. Use the Bash tool exactly once to run: "
    f"`printf {CLAUDE_BASH_PROBE_MARKER}`. Do not use any other tools or modify files. "
    f"After Bash succeeds, reply exactly: {RUNTIME_PROBE_MARKER}"
)


class RuntimeProbeRunner(Protocol):
    run_dir: Path
    run_id: str
    task_timeout: float
    model: str
    agent: Any
    cancellation_check: Callable[[], bool] | None

    def record_event(self, event: dict) -> None: ...


@dataclass(frozen=True)
class RuntimeReadiness:
    """One bounded, unscored check that a harness can complete headlessly."""

    ready: bool
    kind: str
    message: str
    duration_seconds: float
    returncode: int | None = None
    stdout: str | None = None
    stderr: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "ready" if self.ready else "blocked",
            "kind": self.kind,
            "message": self.message,
            "duration_seconds": self.duration_seconds,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }

    def task_reason(self) -> dict[str, object]:
        return {"runtime_readiness": self.to_dict()}


def _result(
    runner: RuntimeProbeRunner,
    *,
    ready: bool,
    kind: str,
    message: str,
    started: float,
    returncode: int | None,
    stdout_path: Path,
    stderr_path: Path,
) -> RuntimeReadiness:
    result = RuntimeReadiness(
        ready=ready,
        kind=kind,
        message=message,
        duration_seconds=max(0.0, time.monotonic() - started),
        returncode=returncode,
        stdout=str(stdout_path),
        stderr=str(stderr_path),
    )
    runner.record_event({
        "event": "harness_runtime_probe",
        "status": "ready" if ready else "blocked",
        "kind": kind,
        "duration": result.duration_seconds,
        "returncode": returncode,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    })
    return result


def _probe_prompt(adapter_name: str) -> str:
    if adapter_name == "claude":
        return CLAUDE_RUNTIME_PROBE_PROMPT
    return RUNTIME_PROBE_PROMPT


def _goose_assistant_text(stream_text: str) -> str:
    """Reassemble assistant text chunks from Goose ``stream-json`` output.

    Goose may split even a short response across multiple NDJSON message events.
    Readiness needs the reconstructed model response, while normal telemetry
    intentionally continues to discard message text.
    """
    chunks: list[str] = []
    for line in stream_text.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        message = item.get("message")
        if not isinstance(message, dict):
            continue
        if str(message.get("role", "")).strip().lower() != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "text":
                continue
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


def _claude_probe_evidence(stream_text: str) -> tuple[str, bool]:
    """Return reconstructed assistant text and proof of one successful Bash probe."""
    assistant_chunks: list[str] = []
    bash_calls: set[str] = set()
    bash_succeeded = False

    for line in stream_text.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue

        message = item.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue

        if item.get("type") == "assistant":
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        assistant_chunks.append(text)
                elif part.get("type") == "tool_use" and part.get("name") == "Bash":
                    call_id = part.get("id")
                    if call_id is not None:
                        bash_calls.add(str(call_id))
        elif item.get("type") == "user":
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "tool_result":
                    continue
                call_id = part.get("tool_use_id")
                if call_id is None or str(call_id) not in bash_calls or part.get("is_error") is True:
                    continue
                result_text = part.get("content")
                if isinstance(result_text, str) and CLAUDE_BASH_PROBE_MARKER in result_text:
                    bash_succeeded = True

    return "".join(assistant_chunks), bash_succeeded


def _read_stdout(stdout_path: Path) -> str | None:
    try:
        return stdout_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _has_model_ready_marker(stdout_path: Path, *, adapter_name: str) -> bool:
    """Require evidence that the model, not merely the CLI, completed the probe."""
    stdout = _read_stdout(stdout_path)
    if stdout is None:
        return False

    if adapter_name == "goose":
        return RUNTIME_PROBE_MARKER in _goose_assistant_text(stdout)
    if adapter_name == "claude":
        assistant_text, _ = _claude_probe_evidence(stdout)
        return RUNTIME_PROBE_MARKER in assistant_text
    return RUNTIME_PROBE_MARKER in stdout


def _has_required_tool_evidence(stdout_path: Path, *, adapter_name: str) -> bool:
    if adapter_name != "claude":
        return True
    stdout = _read_stdout(stdout_path)
    if stdout is None:
        return False
    _, bash_succeeded = _claude_probe_evidence(stdout)
    return bash_succeeded


def probe_runtime_readiness(runner: RuntimeProbeRunner) -> RuntimeReadiness:
    """Exercise the real harness launch boundary with a bounded trivial request.

    The probe deliberately uses the same adapter, custom-command override,
    Bubblewrap plan and environment builder as a scored task. Its workspace is
    separate and deleted afterwards, and no server metrics or task score are
    collected. A failed probe therefore represents runtime/configuration health,
    not model capability. Harness-specific probes may additionally exercise a
    critical tool path when plain inference would not validate task readiness.
    """

    cancellation_check = runner.cancellation_check
    if cancellation_check is not None and cancellation_check():
        raise RunCancelled("Benchmark run cancelled")

    adapter_name = runner.agent.name
    probe_prompt = _probe_prompt(adapter_name)
    timeout = min(float(runner.task_timeout), RUNTIME_PROBE_TIMEOUT_SECONDS)
    workspace = runner.run_dir / "workspaces" / RUNTIME_PROBE_TASK_ID
    shutil.rmtree(workspace, ignore_errors=True)
    workspace.mkdir(parents=True, exist_ok=True)
    logs = runner.run_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout_path = logs / "runtime_probe.stdout.log"
    stderr_path = logs / "runtime_probe.stderr.log"
    stdout_path.unlink(missing_ok=True)
    stderr_path.unlink(missing_ok=True)
    started = time.monotonic()

    try:
        prepared = prepare_harness_process(
            adapter_name=adapter_name,
            adapter=runner.agent.adapter,
            prompt=probe_prompt,
            workspace=workspace,
            model=runner.model,
            extra_environment={
                "AIOS_BENCH_TASK_ID": RUNTIME_PROBE_TASK_ID,
                "AIOS_BENCH_AGENT": adapter_name,
                "AIOS_BENCH_MODEL": runner.model,
                "AIOS_BENCH_RUN_ID": runner.run_id,
                "AIOS_BENCH_TASK_TIMEOUT_SECONDS": str(timeout),
                "AIOS_BENCH_RUNTIME_PROBE": "1",
            },
        )

        if isinstance(runner.agent.adapter, PiAgentAdapter):
            outcome = PiRPCClient(
                runner.model,
                workspace,
                timeout,
                environment=prepared.environment,
                command=prepared.command,
                runaway_check=None,
                cancellation_check=cancellation_check,
            ).run(probe_prompt)
            stdout_path.write_text(outcome.stdout, encoding="utf-8")
            stderr_path.write_text(outcome.stderr, encoding="utf-8")
            if outcome.cancelled:
                raise RunCancelled("Benchmark run cancelled")
            if outcome.timed_out:
                return _result(
                    runner,
                    ready=False,
                    kind="timeout",
                    message=f"runtime probe did not complete within {timeout:.0f}s",
                    started=started,
                    returncode=outcome.returncode,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                )
            if outcome.runaway:
                return _result(
                    runner,
                    ready=False,
                    kind="runaway",
                    message="runtime probe exceeded its bounded execution guard",
                    started=started,
                    returncode=outcome.returncode,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                )
            returncode = outcome.returncode
        else:
            with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr:
                outcome = run_owned(
                    prepared.command,
                    cwd=workspace,
                    env=prepared.environment,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                    timeout=timeout,
                    cancellation_check=cancellation_check,
                )
            if outcome.cancelled:
                raise RunCancelled("Benchmark run cancelled")
            if outcome.timed_out:
                return _result(
                    runner,
                    ready=False,
                    kind="timeout",
                    message=f"runtime probe did not complete within {timeout:.0f}s",
                    started=started,
                    returncode=outcome.returncode,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                )
            returncode = outcome.returncode

        if returncode != 0:
            return _result(
                runner,
                ready=False,
                kind="process_exit",
                message=f"runtime probe exited with code {returncode}",
                started=started,
                returncode=returncode,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
        if not _has_required_tool_evidence(stdout_path, adapter_name=adapter_name):
            return _result(
                runner,
                ready=False,
                kind="tool_probe_failed",
                message="runtime inference succeeded but the required harness tool path did not",
                started=started,
                returncode=returncode,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
        if not _has_model_ready_marker(stdout_path, adapter_name=adapter_name):
            return _result(
                runner,
                ready=False,
                kind="invalid_probe_response",
                message="runtime exited successfully without the model readiness marker",
                started=started,
                returncode=returncode,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
        return _result(
            runner,
            ready=True,
            kind="ready",
            message="headless runtime probe completed successfully",
            started=started,
            returncode=returncode,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    except RunCancelled:
        raise
    except FileNotFoundError as exc:
        return _result(
            runner,
            ready=False,
            kind="unavailable",
            message=f"runtime executable unavailable: {exc}",
            started=started,
            returncode=None,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    except Exception as exc:
        return _result(
            runner,
            ready=False,
            kind="probe_error",
            message=f"runtime probe setup failed: {type(exc).__name__}",
            started=started,
            returncode=None,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
