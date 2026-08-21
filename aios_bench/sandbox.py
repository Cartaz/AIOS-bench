from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SandboxPlan:
    strategy: str
    command_prefix: tuple[str, ...] = ()
    write_confined: bool = False
    grader_hidden: bool = False

    def wrap(self, command: list[str]) -> list[str]:
        return [*self.command_prefix, *command]


def _benchmark_owned_paths() -> tuple[list[Path], list[Path]]:
    root = Path(__file__).resolve().parents[1]
    candidates = (
        root / ".git",
        root / "benchmarks",
        root / "tests",
        root / "aios_bench" / "__pycache__",
    )
    hidden_directories = [path for path in candidates if path.exists()]
    hidden_files = sorted((root / "aios_bench").glob("reference_checks*.py"))
    return hidden_directories, hidden_files


def workspace_sandbox(adapter_name: str, workspace: Path, mode: str | None = None) -> SandboxPlan:
    """Return a cross-harness confinement plan.

    On Linux, local harnesses run below a read-only host root with only the task
    workspace and /tmp writable. Benchmark-owned catalogs, tests, grader source,
    grader bytecode and repository history are masked from the child so read-only
    access cannot reveal deterministic oracle implementation details.
    """
    selected = (mode or os.environ.get("AIOS_BENCH_SANDBOX", "auto")).strip().lower()
    if selected not in {"auto", "required", "off"}:
        raise ValueError("AIOS_BENCH_SANDBOX must be auto, required or off")
    if selected == "off":
        return SandboxPlan("disabled", write_confined=False, grader_hidden=False)
    executable = shutil.which("bwrap")
    if executable:
        root = str(workspace.resolve())
        prefix: tuple[str, ...] = (
            executable, "--die-with-parent", "--new-session",
            "--ro-bind", "/", "/", "--tmpfs", "/tmp",
        )
        hidden_directories, hidden_files = _benchmark_owned_paths()
        for path in hidden_directories:
            prefix += ("--tmpfs", str(path.resolve()))
        for path in hidden_files:
            prefix += ("--ro-bind", "/dev/null", str(path.resolve()))
        grader_hidden = bool(hidden_directories or hidden_files)
        if adapter_name == "piagent":
            pi_state = Path.home() / ".pi" / "agent"
            if pi_state.is_dir():
                state = str(pi_state.resolve())
                prefix += ("--overlay-src", state, "--tmp-overlay", state)
        prefix += (
            "--bind", root, root,
            "--proc", "/proc", "--dev", "/dev",
            "--chdir", root, "--",
        )
        strategy = (
            "bubblewrap_readonly_root_grader_hidden"
            if grader_hidden else "bubblewrap_readonly_root"
        )
        return SandboxPlan(strategy, prefix, write_confined=True, grader_hidden=grader_hidden)
    if selected == "required":
        raise RuntimeError("workspace sandbox required but bubblewrap is unavailable")
    return SandboxPlan("cwd_only_unconfined", write_confined=False, grader_hidden=False)
