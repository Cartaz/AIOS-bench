from __future__ import annotations

import os
import signal
import subprocess
from typing import Any


def spawn_owned(command: list[str], **kwargs: Any) -> subprocess.Popen:
    """Start a child owned by AIOS-Bench, isolated in its own POSIX session."""
    if os.name == "posix":
        kwargs.setdefault("start_new_session", True)
    return subprocess.Popen(command, **kwargs)


def terminate_owned(process: subprocess.Popen, *, grace_seconds: float = 2.0) -> None:
    """Terminate the complete owned process group with a bounded hard-kill fallback."""
    if process.poll() is not None:
        return

    process_group: int | None = None
    if os.name == "posix":
        try:
            process_group = os.getpgid(process.pid)
            os.killpg(process_group, signal.SIGTERM)
        except ProcessLookupError:
            return
    else:
        process.terminate()

    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass

    if os.name == "posix" and process_group is not None:
        # The direct child can exit while one of its descendants survives.
        # Clear the original group before returning so the benchmark never
        # abandons processes it started.
        try:
            os.killpg(process_group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()

    if process.poll() is None:
        process.wait(timeout=grace_seconds)
