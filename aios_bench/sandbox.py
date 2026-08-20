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

    def wrap(self, command: list[str]) -> list[str]:
        return [*self.command_prefix, *command]


def _opencode_state_dirs() -> tuple[Path, ...]:
    home = Path.home()
    data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))
    return (
        data_home / "opencode",
        config_home / "opencode",
        cache_home / "opencode",
    )


def _ephemeral_state_dirs(adapter_name: str) -> tuple[Path, ...]:
    if adapter_name == "piagent":
        return (Path.home() / ".pi" / "agent",)
    if adapter_name == "opencode":
        return _opencode_state_dirs()
    return ()


def workspace_sandbox(adapter_name: str, workspace: Path, mode: str | None = None) -> SandboxPlan:
    """Return a cross-harness write-confinement plan.

    On Linux, local harnesses run under bubblewrap with a read-only root and
    only the task workspace and /tmp writable. Harness state directories that
    need runtime lock/session writes are mounted as temporary overlays so the
    host configuration remains visible while benchmark writes are discarded.
    Network remains shared for research tasks.
    """

    selected = (mode or os.environ.get("AIOS_BENCH_SANDBOX", "auto")).strip().lower()
    if selected not in {"auto", "required", "off"}:
        raise ValueError("AIOS_BENCH_SANDBOX must be auto, required or off")
    if selected == "off":
        return SandboxPlan("disabled", write_confined=False)
    executable = shutil.which("bwrap")
    if executable:
        root = str(workspace.resolve())
        prefix: tuple[str, ...] = (
            executable, "--die-with-parent", "--new-session",
            "--ro-bind", "/", "/", "--tmpfs", "/tmp",
        )
        for state_dir in _ephemeral_state_dirs(adapter_name):
            if state_dir.is_dir():
                state = str(state_dir.resolve())
                prefix += ("--overlay-src", state, "--tmp-overlay", state)
        prefix += (
            "--bind", root, root,
            "--proc", "/proc", "--dev", "/dev",
            "--chdir", root, "--",
        )
        return SandboxPlan("bubblewrap_readonly_root", prefix, write_confined=True)
    if selected == "required":
        raise RuntimeError("workspace sandbox required but bubblewrap is unavailable")
    return SandboxPlan("cwd_only_unconfined", write_confined=False)
