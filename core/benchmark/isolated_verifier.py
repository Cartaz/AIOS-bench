"""Bounded, grader-hidden execution of benchmark workspace Python programs.

Only verification code calls this helper. The agent never receives the hidden
cases or the invocation's host-side data except through its own stdout/stderr.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .sandbox import workspace_sandbox


def run_isolated_python(
    workspace: Path,
    arguments: list[str],
    *,
    stdin: str = "",
    timeout: float = 15.0,
) -> tuple[int, str, str, bool]:
    """Return (code, stdout, bounded stderr, truly sandboxed).

    Never execute candidate code without Bubblewrap's grader-hidden isolation.
    """
    plan = workspace_sandbox("blackbox-verifier", workspace)
    if not plan.grader_hidden:
        return 126, "", "grader-hidden bubblewrap sandbox unavailable", False
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONHASHSEED": "0",
    }
    python = Path(getattr(sys, "_base_executable", None) or sys.executable).resolve()
    try:
        result = subprocess.run(
            plan.wrap([str(python), "-I", *arguments]),
            cwd=workspace,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return 124, out, (err + "\nverification timeout")[-4000:], True
    except OSError as exc:
        return 126, "", f"{type(exc).__name__}: {exc}", True
    return result.returncode, result.stdout, result.stderr[-4000:], True
