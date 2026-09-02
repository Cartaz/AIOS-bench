from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .deepseek_runtime import DEEPSEEK_SANDBOX_HOME, settings_path as deepseek_settings_path
from .paths import BENCHMARK_PACKAGE_ROOT, REPO_ROOT


_WORKSPACE_ALIAS = Path("/tmp/aios-bench-workspace")


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
        # Custom result roots and tests may live outside the repository. In that
        # case hiding the repo cannot cover the workspace, so a direct bind is
        # sufficient and avoids imposing a repository-layout requirement on the
        # runner interface.
        return (
            "--tmpfs", str(repo),
            "--bind", str(workspace), str(workspace),
            "--chdir", str(workspace),
        )

    # Preserve the writable workspace below the private /tmp mount before
    # replacing the repository. The host root is read-only in the sandbox, so
    # aliases directly below / cannot be created. Bubblewrap also resolves bind
    # sources from the parent namespace, which rules out rebinding the alias as
    # a later source. Recreate only the canonical parent directories and restore
    # the canonical workspace path with a sandbox-local symlink to the alias.
    args: tuple[str, ...] = (
        "--dir", str(_WORKSPACE_ALIAS),
        "--bind", str(workspace), str(_WORKSPACE_ALIAS),
        "--tmpfs", str(repo),
    )
    current = repo
    for part in relative.parts[:-1]:
        current /= part
        args += ("--dir", str(current))
    args += (
        "--symlink", str(_WORKSPACE_ALIAS), str(workspace),
        "--chdir", str(workspace),
    )
    return args


def _remote_transport_args(workspace: Path) -> tuple[tuple[str, ...], bool]:
    """Mask grader material while retaining package code for the Agent Zero client.

    Agent Zero's model executes in a separately isolated service/project and
    never receives host paths. The local subprocess is trusted transport code,
    so it retains only the package required for ``python -m`` while benchmark-owned
    answers, fixtures, docs and result history remain masked.
    """
    prefix: tuple[str, ...] = ()
    hidden_directories, hidden_files = _benchmark_owned_paths(workspace)
    for path in hidden_directories:
        prefix += ("--tmpfs", str(path.resolve()))
    for path in hidden_files:
        prefix += ("--ro-bind", "/dev/null", str(path.resolve()))
    return prefix, bool(hidden_directories or hidden_files)


def _deepseek_home_args(workspace: Path) -> tuple[str, ...]:
    """Mount only benchmark-owned non-secret settings into a fresh DSH_HOME.

    Bubblewrap's private ``/tmp`` owns profiles, sessions and all other mutable
    DeepSeek Harness state. The retained settings source stays outside the
    agent-visible repository view and is mounted read-only, so a task cannot
    rewrite the pinned endpoint/model for the active process.
    """

    source = deepseek_settings_path(workspace)
    if not source.is_file():
        raise RuntimeError(f"DeepSeek Harness settings are missing: {source}")
    home = DEEPSEEK_SANDBOX_HOME
    target = home / source.name
    return (
        "--dir", str(home),
        "--ro-bind", str(source.resolve()), str(target),
    )


def workspace_sandbox(adapter_name: str, workspace: Path, mode: str | None = None) -> SandboxPlan:
    """Return a cross-harness confinement plan.

    Local harnesses receive a read-only host plus one writable task workspace;
    the AIOS-bench repository itself is replaced by an empty tmpfs and therefore
    cannot leak golden solutions, graders, docs or prior results. Agent Zero is
    a special transport case: its model runs in a separately isolated service,
    while the trusted local client retains only the package access it needs and
    masks benchmark-owned answer material explicitly. DeepSeek Harness receives
    a private process-lifetime DSH_HOME in the sandbox's tmpfs, seeded only with
    a read-only benchmark-owned provider/model settings document and therefore
    requires Bubblewrap rather than falling back to ambient harness state. Hidden
    black-box verifier processes additionally receive private network and PID
    namespaces so reconstructed code cannot depend on a live endpoint or inspect
    the grader's host process tree during hidden evaluation.
    """
    selected = (mode or os.environ.get("AIOS_BENCH_SANDBOX", "auto")).strip().lower()
    if selected not in {"auto", "required", "off"}:
        raise ValueError("AIOS_BENCH_SANDBOX must be auto, required or off")
    if selected == "off":
        if adapter_name == "deepseek":
            raise RuntimeError(
                "DeepSeek Harness requires the AIOS-Bench Bubblewrap sandbox "
                "for its isolated DSH_HOME"
            )
        return SandboxPlan("disabled", write_confined=False, grader_hidden=False)

    executable = shutil.which("bwrap")
    if executable:
        workspace = workspace.resolve()
        prefix: tuple[str, ...] = (
            executable, "--die-with-parent", "--new-session",
            "--ro-bind", "/", "/", "--tmpfs", "/tmp",
        )

        if adapter_name == "agentzero":
            masks, grader_hidden = _remote_transport_args(workspace)
            prefix += masks
            strategy = "bubblewrap_remote_transport_grader_hidden"
        else:
            prefix += _workspace_rebind_args(workspace)
            grader_hidden = True
            strategy = "bubblewrap_repo_hidden_workspace_only"

        if adapter_name == "deepseek":
            prefix += _deepseek_home_args(workspace)
            strategy += "_deepseek_ephemeral_home"

        if adapter_name == "blackbox-verifier":
            prefix += ("--unshare-net", "--unshare-pid")
            strategy += "_network_pid_isolated"

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
            prefix += ("--chdir", str(workspace),)

        prefix += ("--proc", "/proc", "--dev", "/dev", "--")
        if agentzero_bridge:
            strategy += "_agentzero_project_bridge"
        return SandboxPlan(strategy, prefix, write_confined=True, grader_hidden=grader_hidden)

    if selected == "required" or adapter_name == "deepseek":
        requirement = "DeepSeek Harness isolation" if adapter_name == "deepseek" else "workspace sandbox"
        raise RuntimeError(f"{requirement} requires bubblewrap but it is unavailable")
    return SandboxPlan("cwd_only_unconfined", write_confined=False, grader_hidden=False)
