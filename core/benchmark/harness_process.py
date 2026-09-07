from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .adapters import Adapter, AgentInvocation
from .runtime_paths import with_project_bin
from .sandbox import SandboxPlan, workspace_sandbox


_CLAUDE_RUNTIME_ROOT = "/tmp/aios-bench-claude"
_CLAUDE_INHERITED_ENVIRONMENT_KEYS = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "COLORTERM",
    "TZ",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
)
# ENV_SCRUB hardening forces Claude Code back to its default permission mode
# unless allowedTools is declared in settings (the CLI --allowedTools flag alone
# does not satisfy that gate). These are the native tool families AIOS-Bench
# expects Claude to use unattended inside the outer workspace sandbox.
_CLAUDE_ALLOWED_TOOLS = (
    "Bash",
    "Edit",
    "NotebookEdit",
    "Read",
    "Task",
    "WebFetch",
    "WebSearch",
    "Write",
)
_CLAUDE_SETTINGS_JSON = json.dumps(
    {"allowedTools": list(_CLAUDE_ALLOWED_TOOLS)},
    separators=(",", ":"),
)


@dataclass(frozen=True)
class PreparedHarnessProcess:
    """Fully resolved local harness launch, before benchmark-owned services start."""

    invocation: AgentInvocation
    command: list[str]
    environment: dict[str, str]
    sandbox: SandboxPlan


def _base_environment(adapter_name: str) -> dict[str, str]:
    """Return the host environment intentionally inherited by one harness.

    Most harnesses still rely on their existing ambient-environment contract.
    Claude is different: its subprocess credential scrub derives Bubblewrap mask
    paths from the parent environment. Passing unrelated harness state (for
    example an ``OPENCODE_CONFIG_DIR`` below the read-only host home) can make
    Claude's Bash sandbox fail before the requested command starts. Give Claude
    only process/runtime values it actually needs; adapter-owned configuration is
    merged afterwards.
    """
    if adapter_name != "claude":
        return with_project_bin()

    inherited = {
        key: value
        for key in _CLAUDE_INHERITED_ENVIRONMENT_KEYS
        if (value := os.environ.get(key))
    }
    return with_project_bin(inherited)


def _apply_harness_command_policy(adapter_name: str, command: list[str]) -> list[str]:
    """Apply benchmark-owned command settings required for deterministic execution."""
    if adapter_name != "claude":
        return command

    result = list(command)
    if "--settings" in result:
        index = result.index("--settings")
        if index + 1 >= len(result):
            raise RuntimeError("Malformed Claude command: --settings has no value")
        result[index + 1] = _CLAUDE_SETTINGS_JSON
        return result

    # Adapter and custom-command contracts both place the prompt last. Insert the
    # settings immediately before it so the prompt remains the terminal argument.
    insert_at = max(len(result) - 1, 1)
    result[insert_at:insert_at] = ["--settings", _CLAUDE_SETTINGS_JSON]
    return result


def _apply_harness_environment_policy(adapter_name: str, environment: dict[str, str]) -> None:
    """Apply execution-boundary state isolation required by a harness."""
    if adapter_name != "claude":
        return

    # Claude Code's subprocess scrub creates/masks shell and credential paths
    # before Bash executes. Keep every derived user-state path inside the outer
    # Bubblewrap private /tmp. The scrub itself stays enabled, and the real user
    # home remains read-only and absent from Claude's operational environment.
    environment.update(
        {
            "HOME": f"{_CLAUDE_RUNTIME_ROOT}/home",
            "TMPDIR": f"{_CLAUDE_RUNTIME_ROOT}/tmp",
            "XDG_CONFIG_HOME": f"{_CLAUDE_RUNTIME_ROOT}/xdg-config",
            "XDG_DATA_HOME": f"{_CLAUDE_RUNTIME_ROOT}/xdg-data",
            "XDG_STATE_HOME": f"{_CLAUDE_RUNTIME_ROOT}/xdg-state",
            "XDG_CACHE_HOME": f"{_CLAUDE_RUNTIME_ROOT}/xdg-cache",
            "CLAUDE_BASH_NO_LOGIN": "1",
        }
    )


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
    command = _apply_harness_command_policy(adapter_name, command)

    sandbox = workspace_sandbox(adapter_name, workspace)
    environment = _base_environment(adapter_name)
    environment.update(invocation.environment)
    if extra_environment:
        environment.update({str(key): str(value) for key, value in extra_environment.items()})
    _apply_harness_environment_policy(adapter_name, environment)

    return PreparedHarnessProcess(
        invocation=invocation,
        command=sandbox.wrap(command),
        environment=environment,
        sandbox=sandbox,
    )
