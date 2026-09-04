from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .paths import REPO_ROOT
from .processes import run_owned, spawn_owned, terminate_owned
from .runtime_paths import PROJECT_BIN, npm_environment

DEFAULT_NODE_VERSION = "24.20.0"
INSTALL_TIMEOUT_SECONDS = 600.0
VERSION_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class ManagedHarness:
    name: str
    display_name: str
    package: str
    executable: str
    docs: str
    npm_args: tuple[str, ...] = ()
    install_environment: tuple[tuple[str, str], ...] = ()
    version_args: tuple[str, ...] = ("--version",)

    @property
    def install_command(self) -> tuple[str, ...]:
        return ("npm", "install", "-g", *self.npm_args, self.package)


MANAGED_HARNESSES: tuple[ManagedHarness, ...] = (
    ManagedHarness(
        "piagent",
        "Pi Agent",
        "@earendil-works/pi-coding-agent@0.84.4",
        "pi",
        "https://github.com/earendil-works/pi",
        ("--ignore-scripts",),
    ),
    ManagedHarness(
        "opencode",
        "OpenCode",
        "opencode-ai@1.18.26",
        "opencode",
        "https://opencode.ai/docs/",
        ("--allow-scripts=opencode-ai",),
    ),
    ManagedHarness(
        "letta",
        "Letta Code",
        "@letta-ai/letta-code@0.31.11",
        "letta",
        "https://github.com/letta-ai/letta-code",
        install_environment=(
            ("SHARP_IGNORE_GLOBAL_LIBVIPS", "1"),
            ("NPM_CONFIG_INCLUDE", "optional"),
        ),
    ),
    ManagedHarness(
        "claude",
        "Claude Code",
        "@anthropic-ai/claude-code@2.1.236",
        "claude",
        "https://code.claude.com/docs/",
    ),
    ManagedHarness(
        "deepseek",
        "DeepSeek Harness",
        "@deepseek-ai/dsh@0.1.2-alpha.5",
        "dsh",
        "https://github.com/deepseek-ai/deepseek-harness",
    ),
)
MANAGED_HARNESS_BY_NAME = {item.name: item for item in MANAGED_HARNESSES}


def _first_output_line(command: list[str], *, timeout: float = VERSION_TIMEOUT_SECONDS) -> str | None:
    process: subprocess.Popen[str] | None = None
    try:
        process = spawn_owned(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate(timeout=timeout)
        if process.returncode != 0:
            return None
        lines = (stdout.strip() or stderr.strip()).splitlines()
        return lines[0].strip() if lines else None
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        if process is not None:
            terminate_owned(process)


def requested_node_version() -> str:
    return os.environ.get("AIOS_BENCH_NODE_VERSION", DEFAULT_NODE_VERSION).strip() or DEFAULT_NODE_VERSION


def ensure_project_node(
    *,
    cancellation_check: Callable[[], bool] | None = None,
) -> str:
    """Install/repair the pinned Node runtime inside the Python virtualenv."""
    wanted = requested_node_version()
    node = PROJECT_BIN / "node"
    current = _first_output_line([str(node), "--version"]) if node.is_file() else None
    if current == f"v{wanted}":
        print(f"[OK] Project-local Node {current} already installed")
        return current

    print(f"[INFO] Installing project-local Node v{wanted} into .venv")
    command = [
        sys.executable,
        "-m",
        "nodeenv",
        "-p",
        f"--node={wanted}",
        "--prebuilt",
    ]
    if node.exists():
        command.append("--force")
    outcome = run_owned(
        command,
        cwd=REPO_ROOT,
        timeout=INSTALL_TIMEOUT_SECONDS,
        cancellation_check=cancellation_check,
    )
    if outcome.returncode != 0 or outcome.timed_out or outcome.cancelled:
        raise RuntimeError("project-local Node installation failed")

    current = _first_output_line([str(node), "--version"])
    if current != f"v{wanted}":
        raise RuntimeError(
            f"project-local Node verification failed: expected v{wanted}, found {current or 'missing'}"
        )
    print(f"[OK] Project-local Node {current} verified")
    return current


def _install_environment(spec: ManagedHarness) -> dict[str, str]:
    environment = npm_environment()
    environment.update(spec.install_environment)
    return environment


def _verify_harness_runtime(spec: ManagedHarness, executable: Path) -> str:
    version = _first_output_line([str(executable), *spec.version_args])
    if not version:
        raise RuntimeError(
            f"{spec.display_name} executable exists but runtime verification failed: "
            f"{executable} {' '.join(spec.version_args)}"
        )
    return version


def install_managed_harness(
    name: str,
    *,
    ensure_node: bool = True,
    cancellation_check: Callable[[], bool] | None = None,
) -> Path:
    """Install one pinned npm harness into the AIOS-Bench virtualenv."""
    try:
        spec = MANAGED_HARNESS_BY_NAME[name]
    except KeyError as exc:
        raise ValueError(f"Unknown managed harness: {name}") from exc

    if ensure_node:
        ensure_project_node(cancellation_check=cancellation_check)
    npm = PROJECT_BIN / "npm"
    if not npm.is_file():
        raise RuntimeError("project-local npm is unavailable after Node bootstrap")

    print(f"[INFO] Installing {spec.display_name} ({spec.package}) into .venv")
    command = [str(npm), "install", "-g", *spec.npm_args, spec.package]
    outcome = run_owned(
        command,
        env=_install_environment(spec),
        cwd=REPO_ROOT,
        timeout=INSTALL_TIMEOUT_SECONDS,
        cancellation_check=cancellation_check,
    )
    if outcome.returncode != 0 or outcome.timed_out or outcome.cancelled:
        raise RuntimeError(f"{spec.display_name} installation failed")

    executable = PROJECT_BIN / spec.executable
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError(
            f"{spec.display_name} installation completed without executable {executable}"
        )

    version = _verify_harness_runtime(spec, executable)
    print(f"[OK] {spec.display_name} verified ({version}) at {executable}")
    return executable


def install_all_managed_harnesses() -> None:
    ensure_project_node()
    for spec in MANAGED_HARNESSES:
        install_managed_harness(spec.name, ensure_node=False)
    print("[OK] Managed project-local harnesses installed")


def main() -> int:
    try:
        install_all_managed_harnesses()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"[ERROR] Managed runtime bootstrap failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
