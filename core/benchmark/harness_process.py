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
    if extra_environment:
        environment.update({str(key): str(value) for key, value in extra_environment.items()})

    return PreparedHarnessProcess(
        invocation=invocation,
        command=sandbox.wrap(command),
        environment=environment,
        sandbox=sandbox,
    )
