from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .paths import BENCHMARK_PACKAGE_ROOT, REPO_ROOT


@dataclass(frozen=True)
class SandboxPlan:
    strategy: str
    command_prefix: tuple[str, ...] = ()
    write_confined: bool = False
    grader_hidden: bool = False

    def wrap(self, command: list[str]) -> list[str]:
        return [*self.command_prefix, *command]


def _result_history_paths(workspace: Path) -> tuple[list[Path], list[Path]]:
    """Return result/oracle paths that must not be visible to an agent."""
    workspace = workspace.resolve()
    workspaces_dir = workspace.parent
    run_dir = workspaces_dir.parent
    runs_dir = run_dir.parent
    model_dir = runs_dir.parent
    harness_dir = model_dir.parent
    local_root = harness_dir.parent
    if workspaces_dir.name != "workspaces" or runs_dir.name != "runs" or local_root.name != ".local":
        return [], []

    directories: list[Path] = []
    files: list[Path] = []
    directories.extend(path for path in local_root.iterdir() if path.is_dir() and path != harness_dir)
    directories.extend(path for path in harness_dir.iterdir() if path.is_dir() and path != model_dir)
    directories.extend(path for path in runs_dir.iterdir() if path.is_dir() and path != run_dir)
    directories.extend(
        path for path in workspaces_dir.iterdir()
        if path.is_dir() and path.resolve() != workspace
    )
    for name in ("logs", "oracles"):
        directory = run_dir / name
        if directory.is_dir():
            directories.append(directory)
    for name in ("run.json", "results.jsonl", "events.jsonl"):
        path = run_dir / name
        if path.is_file():
            files.append(path)
    return directories, files


def _benchmark_owned_paths(workspace: Path) -> tuple[list[Path], list[Path]]:
    candidates = (
        REPO_ROOT / ".git",
        REPO_ROOT / "benchmarks",
        REPO_ROOT / "tests",
        BENCHMARK_PACKAGE_ROOT / "__pycache__",
    )
    hidden_directories = [path for path in candidates if path.exists()]
    hidden_files = sorted(BENCHMARK_PACKAGE_ROOT.glob("reference_checks*.py"))
    result_directories, result_files = _result_history_paths(workspace)
    hidden_directories.extend(result_directories)
    hidden_files.extend(result_files)
    return hidden_directories, hidden_files


def workspace_sandbox(adapter_name: str, workspace: Path, mode: str | None = None) -> SandboxPlan:
    """Return a cross-harness confinement plan.

    On Linux, local harnesses run below a read-only host root with only the task
    workspace and /tmp writable. Benchmark-owned grader material, generated
    parametric oracles, repository history and historical result workspaces are
    masked from the child.

    Agent Zero's benchmark client additionally needs write access to a dedicated
    shared projects root used only as a filesystem transport into the separately
    isolated Agent Zero service. The model never receives host benchmark paths;
    each task is copied into a fresh Agent Zero project under that root.
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
        hidden_directories, hidden_files = _benchmark_owned_paths(workspace)
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
        agentzero_bridge = False
        if adapter_name == "agentzero":
            configured = os.environ.get("AIOS_BENCH_AGENTZERO_PROJECTS_ROOT", "").strip()
            if configured:
                projects_root = Path(configured).expanduser()
                if projects_root.is_dir():
                    bridge = str(projects_root.resolve())
                    prefix += ("--bind", bridge, bridge)
                    agentzero_bridge = True
        prefix += (
            "--bind", root, root,
            "--proc", "/proc", "--dev", "/dev",
            "--chdir", root, "--",
        )
        strategy = (
            "bubblewrap_readonly_root_grader_hidden"
            if grader_hidden else "bubblewrap_readonly_root"
        )
        if agentzero_bridge:
            strategy += "_agentzero_project_bridge"
        return SandboxPlan(strategy, prefix, write_confined=True, grader_hidden=grader_hidden)
    if selected == "required":
        raise RuntimeError("workspace sandbox required but bubblewrap is unavailable")
    return SandboxPlan("cwd_only_unconfined", write_confined=False, grader_hidden=False)
