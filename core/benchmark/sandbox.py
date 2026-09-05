from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .deepseek_runtime import DEEPSEEK_SANDBOX_HOME, settings_path as deepseek_settings_path
from .local_gateway import profile_source_dir
from .paths import BENCHMARK_PACKAGE_ROOT, REPO_ROOT
from .runtime_paths import PROJECT_VENV


_WORKSPACE_ALIAS = Path("/tmp/aios-bench-workspace")
_RUNTIME_ALIAS = Path("/tmp/aios-bench-runtime")


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


def _project_runtime_args() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Preserve the project-local runtime while the rest of the repo stays hidden.

    Managed npm harnesses are intentionally installed under ``.venv``. Bubblewrap
    later replaces the repository with tmpfs, so the runtime must be captured at
    a neutral read-only alias before that replacement and rebound with a symlink
    afterwards. No benchmark source or result directory is exposed by this bind.
    """
    runtime = PROJECT_VENV.resolve()
    repo = REPO_ROOT.resolve()
    if not runtime.is_dir():
        return (), ()
    try:
        runtime.relative_to(repo)
    except ValueError:
        return (), ()
    before_repo_hide = (
        "--dir", str(_RUNTIME_ALIAS),
        "--ro-bind", str(runtime), str(_RUNTIME_ALIAS),
    )
    after_repo_hide = (
        "--symlink", str(_RUNTIME_ALIAS), str(runtime),
    )
    return before_repo_hide, after_repo_hide


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
    """Mask grader material while retaining package code for the Agent Zero client."""
    prefix: tuple[str, ...] = ()
    hidden_directories, hidden_files = _benchmark_owned_paths(workspace)
    for path in hidden_directories:
        prefix += ("--tmpfs", str(path.resolve()))
    for path in hidden_files:
        prefix += ("--ro-bind", "/dev/null", str(path.resolve()))
    return prefix, bool(hidden_directories or hidden_files)


def _deepseek_home_args(workspace: Path) -> tuple[str, ...]:
    """Mount only benchmark-owned non-secret settings into a fresh DSH_HOME."""
    source = deepseek_settings_path(workspace)
    if not source.is_file():
        raise RuntimeError(f"DeepSeek Harness settings are missing: {source}")
    home = DEEPSEEK_SANDBOX_HOME
    target = home / source.name
    return (
        "--dir", str(home),
        "--ro-bind", str(source.resolve()), str(target),
    )


def _pi_profile_args(workspace: Path) -> tuple[str, ...]:
    """Expose only the benchmark-owned Pi model registry, read-only.

    The source lives next to run metadata and is hidden when the repository is
    replaced by tmpfs. Recreate only its empty parent path inside the sandbox and
    bind the single models.json from the parent namespace as read-only.
    """
    directory = profile_source_dir(workspace, "piagent").resolve()
    source = directory / "models.json"
    if not source.is_file():
        return ()
    run_dir = workspace.resolve().parent.parent
    harness_profiles = run_dir / "harness_profiles"
    task_profiles = harness_profiles / workspace.resolve().name
    return (
        "--dir", str(harness_profiles),
        "--dir", str(task_profiles),
        "--dir", str(directory),
        "--ro-bind", str(source), str(source),
    )


def workspace_sandbox(adapter_name: str, workspace: Path, mode: str | None = None) -> SandboxPlan:
    """Return a cross-harness confinement plan.

    Local harnesses receive a read-only host plus one writable task workspace;
    the AIOS-bench repository itself is replaced by an empty tmpfs and therefore
    cannot leak golden solutions, graders, docs or prior results. The project
    virtualenv is rebound read-only so Doctor-managed executables remain usable
    without exposing repository source. Agent Zero is a special transport case
    whose trusted local client retains package access while benchmark-owned
    answer material is masked. DeepSeek receives a private DSH_HOME whose retained
    settings are captured before repository masking. Pi receives only a read-only
    benchmark-owned models.json when the canonical local-gateway profile is active,
    rather than ambient ~/.pi state.
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

        runtime_before, runtime_after = _project_runtime_args()
        if adapter_name != "agentzero":
            prefix += runtime_before

        # DeepSeek settings live under the owning run directory, which is hidden
        # together with the repository below. Capture that single non-secret file
        # into private /tmp while the source path is still visible.
        if adapter_name == "deepseek":
            prefix += _deepseek_home_args(workspace)

        if adapter_name == "agentzero":
            masks, grader_hidden = _remote_transport_args(workspace)
            prefix += masks
            strategy = "bubblewrap_remote_transport_grader_hidden"
        else:
            prefix += _workspace_rebind_args(workspace)
            prefix += runtime_after
            grader_hidden = True
            strategy = "bubblewrap_repo_hidden_workspace_only"
            if runtime_before:
                strategy += "_project_runtime_readonly"

        if adapter_name == "deepseek":
            strategy += "_deepseek_ephemeral_home"

        if adapter_name == "blackbox-verifier":
            prefix += ("--unshare-net", "--unshare-pid")
            strategy += "_network_pid_isolated"

        if adapter_name == "piagent":
            pi_profile = _pi_profile_args(workspace)
            if pi_profile:
                prefix += pi_profile
                strategy += "_pi_readonly_gateway_profile"
            else:
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

    if selected == "required":
        raise RuntimeError("workspace sandbox required but bubblewrap is unavailable")
    if adapter_name == "deepseek":
        raise RuntimeError("DeepSeek Harness isolation requires bubblewrap but it is unavailable")
    return SandboxPlan("cwd_only_unconfined", write_confined=False, grader_hidden=False)
