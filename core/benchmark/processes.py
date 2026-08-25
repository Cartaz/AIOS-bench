from __future__ import annotations

import os
import signal
import subprocess
from typing import Any


def spawn_owned(command: list[str], **kwargs: Any) -> subprocess.Popen:
    """Start a child owned by AIOS-Bench, isolated in its own POSIX session."""
    if os.name == "posix":
        kwargs.setdefault("start_new_session", True)
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
