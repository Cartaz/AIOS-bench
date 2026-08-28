from __future__ import annotations

import json
import os
import selectors
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .processes import spawn_owned, terminate_owned


@dataclass
class PiRPCResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    runaway: bool = False
    cancelled: bool = False


class PiRPCClient:
    """Small stdio JSONL client for pi --mode rpc."""

    def __init__(
        self,
        model: str,
        workspace: Path,
        timeout: float,
        environment: dict[str, str] | None = None,
        extra_args: list[str] | None = None,
        command: list[str] | None = None,
        runaway_check: Callable[[], bool] | None = None,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> None:
        self.model = model
        self.workspace = workspace
        self.timeout = timeout
        self.environment = environment or {}
        self.extra_args = list(extra_args or [])
        self.command = list(command) if command is not None else None
        self.runaway_check = runaway_check
        self.cancellation_check = cancellation_check

    def _command(self) -> list[str]:
        if self.command is not None:
            return list(self.command)
        command = ["pi", "--mode", "rpc", "--no-session"]
        if self.model and self.model != "unknown":
            command += ["--model", self.model]
        command += self.extra_args
        return command

    @staticmethod
    def _drain_stream(stream, chunks: list[str]) -> None:
        try:
            for chunk in iter(stream.readline, ""):
                chunks.append(chunk)
        finally:
            stream.close()

    def run(self, prompt: str) -> PiRPCResult:
        env = os.environ.copy()
        env.update(self.environment)
        env["AIOS_BENCH_WORKSPACE"] = str(self.workspace.resolve())
        proc = spawn_owned(
            self._command(),
            cwd=self.workspace,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if proc.stdin is None or proc.stdout is None or proc.stderr is None:
            terminate_owned(proc)
            raise RuntimeError("Pi RPC process did not expose the required stdio pipes")

        started = time.monotonic()
        lines: list[str] = []
        stderr_chunks: list[str] = []
        timed_out = False
        runaway = False
        cancelled = False
        protocol_succeeded = False
        protocol_failed = False
        selector = selectors.DefaultSelector()
        stderr_thread: threading.Thread | None = None
        try:
            stderr_thread = threading.Thread(
                target=self._drain_stream,
                args=(proc.stderr, stderr_chunks),
                name="aios-bench-pi-stderr",
                daemon=True,
            )
            stderr_thread.start()
            proc.stdin.write(
                json.dumps({"id": "aios-bench", "type": "prompt", "message": prompt}) + "\n"
            )
            proc.stdin.flush()
            selector.register(proc.stdout, selectors.EVENT_READ)
            while True:
                remaining = self.timeout - (time.monotonic() - started)
                if remaining <= 0:
                    timed_out = True
                    break
                if self.cancellation_check is not None and self.cancellation_check():
                    cancelled = True
                    break
                if self.runaway_check is not None and self.runaway_check():
                    runaway = True
                    break
                ready = selector.select(timeout=min(remaining, 0.25))
                if not ready:
                    if proc.poll() is not None:
                        break
                    continue
                line = proc.stdout.readline()
                if line:
                    lines.append(line)
                    try:
                        event: dict[str, Any] = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if (
                        event.get("type") == "response"
                        and event.get("command") == "prompt"
                        and event.get("success") is False
                    ):
                        protocol_failed = True
                        break
                    if event.get("type") == "agent_settled":
                        protocol_succeeded = True
                        break
                    if event.get("type") == "auto_retry_end" and event.get("success") is False:
                        protocol_failed = True
                        break
                elif proc.poll() is not None:
                    break
        finally:
            selector.close()
            if not proc.stdin.closed:
                proc.stdin.close()
            terminate_owned(proc)
            if stderr_thread is not None:
                stderr_thread.join(timeout=1.0)
        if timed_out or runaway or cancelled or protocol_failed:
            returncode = 1
        elif protocol_succeeded:
            returncode = 0
        else:
            returncode = proc.returncode if proc.returncode is not None else 1
        return PiRPCResult(
            returncode,
            "".join(lines),
            "".join(stderr_chunks),
            timed_out,
            runaway,
            cancelled,
        )
