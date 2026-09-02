from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable

from .runtime_paths import with_project_bin


@dataclass(frozen=True)
class OwnedProcessOutcome:
    returncode: int
    timed_out: bool = False
    cancelled: bool = False


def spawn_owned(command: list[str], **kwargs: Any) -> subprocess.Popen:
    """Start a child owned by AIOS-Bench, isolated in its own POSIX session.

    Project-local harness runtimes in ``.venv/bin`` are always preferred over
    ambient system installations. This keeps ordinary ``.venv/bin/python``
    launches reproducible without requiring shell activation.
    """
    if os.name == "posix":
        kwargs.setdefault("start_new_session", True)
    kwargs["env"] = with_project_bin(kwargs.get("env"))
    process = subprocess.Popen(command, **kwargs)
    if os.name == "posix" and kwargs.get("start_new_session"):
        # A new session makes the child's PID the process-group ID. Persist it
        # because the direct child can exit before descendants are cleaned up.
        setattr(process, "_aios_process_group", process.pid)
    return process


def terminate_owned(process: subprocess.Popen, *, grace_seconds: float = 2.0) -> None:
    """Terminate every process owned by one launch with a bounded fallback."""
    if getattr(process, "_aios_cleanup_done", False):
        return

    process_group = getattr(process, "_aios_process_group", None)
    try:
        if os.name == "posix" and process_group is not None:
            if process.poll() is None:
                try:
                    os.killpg(process_group, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=grace_seconds)
                except subprocess.TimeoutExpired:
                    pass

            # The parent may already have exited while a descendant remains in
            # the original group. Always clear that group before returning.
            try:
                os.killpg(process_group, signal.SIGKILL)
            except ProcessLookupError:
                pass

            if process.poll() is None:
                process.wait(timeout=grace_seconds)
            return

        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=grace_seconds)
    finally:
        setattr(process, "_aios_cleanup_done", True)


def run_owned(
    command: list[str],
    *,
    timeout: float | None = None,
    cancellation_check: Callable[[], bool] | None = None,
    poll_interval: float = 0.1,
    **kwargs: Any,
) -> OwnedProcessOutcome:
    """Run an owned process with bounded timeout/cancellation semantics.

    This is the canonical primitive for application-owned external commands.
    It never uses a shell, polls cancellation without blocking the caller
    indefinitely and always performs process-group cleanup before returning.
    """
    process = spawn_owned(command, **kwargs)
    started = time.monotonic()
    timed_out = False
    cancelled = False
    try:
        while process.poll() is None:
            if cancellation_check is not None and cancellation_check():
                cancelled = True
                break
            if timeout is not None and time.monotonic() - started >= timeout:
                timed_out = True
                break
            try:
                process.wait(timeout=poll_interval)
            except subprocess.TimeoutExpired:
                pass
    finally:
        terminate_owned(process)
    return OwnedProcessOutcome(
        process.returncode if process.returncode is not None else 1,
        timed_out=timed_out,
        cancelled=cancelled,
    )
