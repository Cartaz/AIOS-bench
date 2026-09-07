from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .adapters import Adapter, AgentInvocation
from .runtime_paths import with_project_bin
from .sandbox import SandboxPlan, workspace_sandbox


@dataclass(frozen=True)
class PreparedHarnessProcess:
    """Fully resolved local harness launch, before benchmark-owned services start."""

    invocation: AgentInvocation
    command: list[str]
    environment: dict[str, str]
    sandbox: SandboxPlan


def _apply_harness_environment_policy(adapter_name: str, environment: dict[str, str]) -> None:
    """Apply execution-boundary environment isolation required by a harness.

    Claude Code's subprocess credential scrub uses ``$HOME`` as a Bubblewrap
    mask target before Bash commands run. AIOS-Bench deliberately makes the host
    home read-only, so point Claude at the already-private temporary filesystem
    instead. The scrub remains enabled; no real user home or credentials are
    made writable to the harness.
    """
    if adapter_name == "claude":
        environment["HOME"] = "/tmp"


def prepare_harness_process(
    *,
    adapter_name: str,
    adapter: Adapter,
    prompt: str,
    workspace: Path,
    model: str,
    extra_environment: Mapping[str, str] | None = None,
) -> PreparedHarnessProcess:
    """Build one harness process through the canonical execution boundary.

    Task execution and runtime-readiness probes must use the same adapter build,
    custom-command override, Bubblewrap plan and environment composition. Keeping
    this in one module prevents a preflight path from accidentally validating a
    launch shape that differs from the real benchmark.
    """

    invocation = adapter.build(prompt, workspace, model)
    command = list(invocation.command)
    custom = os.environ.get(f"AIOS_BENCH_{adapter_name.upper()}_COMMAND")
    if custom:
        command = [*shlex.split(custom), prompt]

    sandbox = workspace_sandbox(adapter_name, workspace)
    environment = with_project_bin()
    environment.update(invocation.environment)
    _apply_harness_environment_policy(adapter_name, environment)
    if extra_environment:
        environment.update({str(key): str(value) for key, value in extra_environment.items()})

    return PreparedHarnessProcess(
        invocation=invocation,
        command=sandbox.wrap(command),
        environment=environment,
        sandbox=sandbox,
    )
