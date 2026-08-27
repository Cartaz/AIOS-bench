from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class BubblewrapCapability:
    usable: bool
    error: str | None = None


def probe_bubblewrap(executable: str, *, timeout: float = 3.0) -> BubblewrapCapability:
    """Verify that the installed Bubblewrap can create the namespaces we need.

    Presence on PATH is insufficient on restricted hosts such as some CI
    runners. The probe executes no untrusted code and exercises the namespace
    primitives required by the verifier sandbox.
    """
    try:
        process = subprocess.run(
            [
                executable,
                "--die-with-parent",
                "--new-session",
                "--unshare-net",
                "--unshare-pid",
                "--ro-bind",
                "/",
                "/",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--",
                "/bin/true",
            ],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BubblewrapCapability(False, f"{type(exc).__name__}: {exc}")
    if process.returncode == 0:
        return BubblewrapCapability(True, None)
    detail = (process.stderr or process.stdout).strip()[-1000:]
    return BubblewrapCapability(
        False,
        detail or f"bubblewrap probe exited {process.returncode}",
    )


__all__ = ["BubblewrapCapability", "probe_bubblewrap"]
