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


def workspace_sandbox(adapter_name: str, workspace: Path, mode: str | None = None) -> SandboxPlan:
    """Return a cross-harness write-confinement plan.

    Codex supplies its own workspace-write sandbox. On Linux, other local
    harnesses run under bubblewrap with a read-only root and only the task
    workspace and /tmp writable. Network remains shared for research tasks.
    """

    selected = (mode or os.environ.get("AIOS_BENCH_SANDBOX", "auto")).strip().lower()
    if selected not in {"auto", "required", "off"}:
        raise ValueError("AIOS_BENCH_SANDBOX must be auto, required or off")
    if adapter_name == "codex":
        return SandboxPlan("adapter_workspace_write", write_confined=True)
    if selected == "off":
        return SandboxPlan("disabled", write_confined=False)
    executable = shutil.which("bwrap")
    if executable:
        root = str(workspace.resolve())
        prefix: tuple[str, ...] = (
            executable, "--die-with-parent", "--new-session",
            "--ro-bind", "/", "/", "--tmpfs", "/tmp",
        )
        # Pi takes short-lived lock files next to its settings and credential
        # store, even for read-only operations.  A tmp overlay preserves the
        # host files as a read-only lower layer while keeping all runtime
        # writes private to the sandbox and discarding them on exit.
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
        return SandboxPlan("bubblewrap_readonly_root", prefix, write_confined=True)
    if selected == "required":
        raise RuntimeError("workspace sandbox required but bubblewrap is unavailable")
    return SandboxPlan("cwd_only_unconfined", write_confined=False)
