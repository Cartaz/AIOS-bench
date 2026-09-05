import shutil
import subprocess
from pathlib import Path

import pytest

from aios_bench.failures import UNAVAILABLE, classify_failure
from aios_bench.manifest import probe_executable
from aios_bench.sandbox import workspace_sandbox


RUNTIME_ALIAS = "/tmp/aios-bench-runtime"


def _has_sequence(command: list[str], sequence: list[str]) -> bool:
    width = len(sequence)
    return any(
        command[index:index + width] == sequence
        for index in range(len(command) - width + 1)
    )


def _sequence_index(command: list[str], sequence: list[str]) -> int:
    width = len(sequence)
    return next(
        index
        for index in range(len(command) - width + 1)
        if command[index:index + width] == sequence
    )


def test_managed_project_runtime_survives_repository_mask(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    runtime = repo / ".venv"
    (runtime / "bin").mkdir(parents=True)
    workspace = (
        repo / "results" / ".local" / "claude" / "m" / "runs" / "r"
        / "workspaces" / "t"
    )
    workspace.mkdir(parents=True)

    monkeypatch.setattr("aios_bench.sandbox.REPO_ROOT", repo)
    monkeypatch.setattr("aios_bench.sandbox.PROJECT_VENV", runtime)
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")

    command = workspace_sandbox("claude", workspace, "required").wrap(["claude"])

    runtime_bind = ["--ro-bind", str(runtime.resolve()), RUNTIME_ALIAS]
    repo_hide = ["--tmpfs", str(repo.resolve())]
    runtime_restore = ["--symlink", RUNTIME_ALIAS, str(runtime.resolve())]
    assert _has_sequence(command, runtime_bind)
    assert _has_sequence(command, repo_hide)
    assert _has_sequence(command, runtime_restore)
    assert _sequence_index(command, runtime_bind) < _sequence_index(command, repo_hide)
    assert _sequence_index(command, repo_hide) < _sequence_index(command, runtime_restore)


def test_managed_runtime_is_visible_while_repository_remains_hidden(
    monkeypatch,
    tmp_path: Path,
):
    executable = shutil.which("bwrap")
    if executable is None:
        pytest.skip("bubblewrap is unavailable")

    repo = tmp_path / "repo"
    runtime = repo / ".venv"
    runtime_bin = runtime / "bin"
    runtime_bin.mkdir(parents=True)
    marker = runtime_bin / "runtime-marker"
    marker.write_text("managed-runtime-visible", encoding="utf-8")
    workspace = (
        repo / "results" / ".local" / "claude" / "m" / "runs" / "r"
        / "workspaces" / "t"
    )
    workspace.mkdir(parents=True)
    secret = repo / "benchmark-secret.txt"
    secret.write_text("must-not-leak", encoding="utf-8")

    monkeypatch.setattr("aios_bench.sandbox.REPO_ROOT", repo)
    monkeypatch.setattr("aios_bench.sandbox.PROJECT_VENV", runtime)

    command = workspace_sandbox("claude", workspace, "required").wrap([
        "/bin/sh",
        "-c",
        (
            f"test \"$(cat {marker})\" = managed-runtime-visible && "
            f"test ! -e {secret} && "
            "printf workspace-write > runtime-check.txt"
        ),
    ])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    assert (workspace / "runtime-check.txt").read_text(encoding="utf-8") == "workspace-write"
    assert secret.read_text(encoding="utf-8") == "must-not-leak"


def test_manifest_probe_uses_project_local_runtime(monkeypatch, tmp_path: Path):
    project_bin = tmp_path / "bin"
    project_bin.mkdir()
    executable = project_bin / "claude"
    executable.write_text("#!/bin/sh\necho claude-test-1.0\n", encoding="utf-8")
    executable.chmod(0o755)

    monkeypatch.setattr("aios_bench.runtime_paths.PROJECT_BIN", project_bin)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    result = probe_executable("claude")

    assert result["path"] == str(executable)
    assert result["version"] == "claude-test-1.0"
    assert result["probe_status"] == "ok"


def test_missing_harness_is_noncomparable_unavailable_failure():
    assert classify_failure(
        status="unavailable",
        success=False,
        execution_success=False,
        evaluation_passed=None,
    ) == UNAVAILABLE
