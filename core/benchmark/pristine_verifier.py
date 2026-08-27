from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .bubblewrap import probe_bubblewrap


@dataclass(frozen=True)
class VerifierExecution:
    returncode: int
    stdout: str
    stderr: str
    isolation_strategy: str
    filesystem_confined: bool
    network_confined: bool
    isolation_error: str | None = None


def _runtime_binding() -> tuple[tuple[str, ...], str]:
    prefix = Path(sys.prefix).resolve()
    executable = Path(sys.executable).resolve()
    try:
        relative = executable.relative_to(prefix)
    except ValueError:
        return (), str(executable)
    runtime_alias = Path("/aios-verifier-runtime")
    return (
        "--ro-bind",
        str(prefix),
        str(runtime_alias),
    ), str(runtime_alias.joinpath(*relative.parts))


def _system_bindings() -> tuple[str, ...]:
    bindings: tuple[str, ...] = ()
    for raw in ("/usr", "/bin", "/lib", "/lib64", "/sbin"):
        path = Path(raw)
        if path.exists():
            bindings += ("--ro-bind", raw, raw)
    return bindings


def _sandbox_command(pristine: Path, code: str, executable: str) -> list[str]:
    runtime_binding, sandbox_python = _runtime_binding()
    workspace = pristine.resolve()
    return [
        executable,
        "--die-with-parent",
        "--new-session",
        "--unshare-net",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        *_system_bindings(),
        *runtime_binding,
        "--bind",
        str(workspace),
        "/workspace",
        "--tmpfs",
        "/tmp",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--chdir",
        "/workspace",
        "--",
        sandbox_python,
        "-I",
        "-S",
        "-c",
        code,
    ]


def run_pristine_verifier(
    pristine: Path,
    code: str,
    *,
    timeout: float = 8.0,
    mode: str | None = None,
) -> VerifierExecution:
    """Run hidden verification with an explicit, capability-tested boundary."""
    selected = (mode or os.environ.get("AIOS_BENCH_VERIFIER_SANDBOX", "auto")).strip().lower()
    if selected not in {"auto", "required", "off"}:
        raise ValueError("AIOS_BENCH_VERIFIER_SANDBOX must be auto, required or off")

    bootstrap = (
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path.cwd()))\n"
        + code
    )
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }

    bwrap = shutil.which("bwrap") if selected != "off" else None
    capability_error: str | None = None
    usable_bwrap = False
    if bwrap is not None:
        capability = probe_bubblewrap(bwrap)
        usable_bwrap = capability.usable
        capability_error = capability.error

    if usable_bwrap and bwrap is not None:
        command = _sandbox_command(pristine, bootstrap, bwrap)
        cwd = None
        strategy = "bubblewrap_minimal_runtime"
        filesystem_confined = True
        network_confined = True
        isolation_error = None
    else:
        if selected == "required":
            reason = capability_error or "bubblewrap is unavailable"
            raise RuntimeError(f"pristine verifier sandbox required but unavailable: {reason}")
        command = [sys.executable, "-I", "-S", "-c", bootstrap]
        cwd = pristine
        strategy = "isolated_python_unconfined" if selected == "auto" else "sandbox_disabled"
        filesystem_confined = False
        network_confined = False
        isolation_error = capability_error if selected == "auto" else None

    process = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return VerifierExecution(
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
        isolation_strategy=strategy,
        filesystem_confined=filesystem_confined,
        network_confined=network_confined,
        isolation_error=isolation_error,
    )


__all__ = ["VerifierExecution", "run_pristine_verifier"]
