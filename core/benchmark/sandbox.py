from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .bubblewrap import probe_bubblewrap
from .paths import BENCHMARK_PACKAGE_ROOT, REPO_ROOT


_WORKSPACE_ALIAS = Path("/workspace")


@dataclass(frozen=True)
class SandboxPlan:
    strategy: str
    command_prefix: tuple[str, ...] = ()
    write_confined: bool = False
    grader_hidden: bool = False
    isolation_error: str | None = None

    def wrap(self, command: list[str]) -> list[str]:
        return [*self.command_prefix, *command]

    def to_dict(self) -> dict[str, object]:
        """Return public boundary metadata without exposing command/path details."""
        return {
            "strategy": self.strategy,
            "write_confined": self.write_confined,
            "grader_hidden": self.grader_hidden,
            "network_isolation_claimed": False,
            "isolation_error": self.isolation_error,
        }


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
    """Sensitive benchmark paths for transports that must retain package access."""
    candidates = (
        REPO_ROOT / ".git",
        REPO_ROOT / "benchmarks",
        REPO_ROOT / "tests",
        REPO_ROOT / "docs",
        REPO_ROOT / "results",
        BENCHMARK_PACKAGE_ROOT / "__pycache__",
    )
    hidden_directories = [path for path in candidates if path.exists()]
    hidden_files = sorted(BENCHMARK_PACKAGE_ROOT.glob("reference_checks*.py"))
    for name in ("golden_solutions.py", "parametric_goldens.py"):
        path = BENCHMARK_PACKAGE_ROOT / name
        if path.is_file():
            hidden_files.append(path)
    for name in ("Report A.md", "Report B.md"):
        path = REPO_ROOT / name
        if path.is_file():
            hidden_files.append(path)
    result_directories, result_files = _result_history_paths(workspace)
    hidden_directories.extend(result_directories)
    hidden_files.extend(result_files)
    return hidden_directories, hidden_files


def _workspace_rebind_args(workspace: Path) -> tuple[str, ...]:
    """Hide the repository while preserving one writable canonical workspace."""
    workspace = workspace.resolve()
    repo = REPO_ROOT.resolve()
    try:
        relative = workspace.relative_to(repo)
    except ValueError:
        return (
            "--tmpfs", str(repo),
            "--bind", str(workspace), str(workspace),
            "--chdir", str(workspace),
        )

    args: tuple[str, ...] = (
        "--bind", str(workspace), str(_WORKSPACE_ALIAS),
        "--tmpfs", str(repo),
    )
    current = repo
    for part in relative.parts[:-1]:
        current /= part
        args += ("--dir", str(current))
    args += (
        "--bind", str(_WORKSPACE_ALIAS), str(workspace),
        "--chdir", str(workspace),
    )
    return args


def _remote_workspace_rebind_args(workspace: Path) -> tuple[str, ...]:
    """Restore only the current workspace after the remote transport masks results."""
    workspace = workspace.resolve()
    results_root = (REPO_ROOT / "results").resolve()
    try:
        relative = workspace.relative_to(results_root)
    except ValueError:
        return ("--chdir", str(workspace))

    args: tuple[str, ...] = (
        "--bind", str(workspace), str(_WORKSPACE_ALIAS),
    )
    current = results_root
    for part in relative.parts[:-1]:
        current /= part
        args += ("--dir", str(current))
    args += (
        "--bind", str(_WORKSPACE_ALIAS), str(workspace),
        "--chdir", str(workspace),
    )
    return args


def _remote_transport_args(workspace: Path) -> tuple[tuple[str, ...], bool]:
    prefix: tuple[str, ...] = ()
    hidden_directories, hidden_files = _benchmark_owned_paths(workspace)
    for path in hidden_directories:
        prefix += ("--tmpfs", str(path.resolve()))
    for path in hidden_files:
        prefix += ("--ro-bind", "/dev/null", str(path.resolve()))
    return prefix, bool(hidden_directories or hidden_files)


def workspace_sandbox(adapter_name: str, workspace: Path, mode: str | None = None) -> SandboxPlan:
    """Return a capability-tested cross-harness confinement plan."""
    selected = (mode or os.environ.get("AIOS_BENCH_SANDBOX", "auto")).strip().lower()
    if selected not in {"auto", "required", "off"}:
        raise ValueError("AIOS_BENCH_SANDBOX must be auto, required or off")
    if selected == "off":
        return SandboxPlan("disabled", write_confined=False, grader_hidden=False)

    executable = shutil.which("bwrap")
    capability_error: str | None = None
    if executable:
        capability = probe_bubblewrap(executable)
        if not capability.usable:
            capability_error = capability.error
            executable = None

    if executable:
        workspace = workspace.resolve()
        prefix: tuple[str, ...] = (
            executable, "--die-with-parent", "--new-session",
            "--ro-bind", "/", "/", "--tmpfs", "/tmp",
        )

        if adapter_name == "agentzero":
            masks, grader_hidden = _remote_transport_args(workspace)
            prefix += masks
            prefix += _remote_workspace_rebind_args(workspace)
            strategy = "bubblewrap_remote_transport_grader_hidden"
        else:
            prefix += _workspace_rebind_args(workspace)
            grader_hidden = True
            strategy = "bubblewrap_repo_hidden_workspace_only"

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

        prefix += ("--proc", "/proc", "--dev", "/dev", "--")
        if agentzero_bridge:
            strategy += "_agentzero_project_bridge"
        return SandboxPlan(
            strategy,
            prefix,
            write_confined=not agentzero_bridge,
            grader_hidden=grader_hidden,
        )

    if selected == "required":
        reason = capability_error or "bubblewrap is unavailable"
        raise RuntimeError(f"workspace sandbox required but unavailable: {reason}")
    return SandboxPlan(
        "cwd_only_unconfined",
        write_confined=False,
        grader_hidden=False,
        isolation_error=capability_error,
    )
