import shutil
import subprocess
from pathlib import Path

import pytest

from core.benchmark.sandbox import (
    REPO_ROOT,
    _benchmark_owned_paths,
    _result_history_paths,
    workspace_sandbox,
)


def _has_sequence(command: list[str], sequence: list[str]) -> bool:
    width = len(sequence)
    return any(command[index:index + width] == sequence for index in range(len(command) - width + 1))


def test_bubblewrap_hides_repository_and_rebinds_only_workspace(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = repo / "results" / ".local" / "piagent" / "model" / "runs" / "run" / "workspaces" / "task"
    workspace.mkdir(parents=True)
    monkeypatch.setattr("core.benchmark.sandbox.REPO_ROOT", repo)
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")

    plan = workspace_sandbox("piagent", workspace, "required")
    command = plan.wrap(["pi", "--mode", "rpc"])

    assert plan.strategy == "bubblewrap_repo_hidden_workspace_only"
    assert plan.grader_hidden is True
    assert _has_sequence(command, ["--ro-bind", "/", "/"])
    assert _has_sequence(command, ["--bind", str(workspace.resolve()), "/workspace"])
    assert _has_sequence(command, ["--tmpfs", str(repo.resolve())])
    assert _has_sequence(command, ["--bind", "/workspace", str(workspace.resolve())])
    assert _has_sequence(command, ["--chdir", str(workspace.resolve())])
    assert command[-3:] == ["pi", "--mode", "rpc"]


def test_bubblewrap_repository_hidden_contract_executes(monkeypatch, tmp_path: Path):
    executable = shutil.which("bwrap")
    if executable is None:
        pytest.skip("bubblewrap is unavailable")

    repo = tmp_path / "repo"
    workspace = repo / "results" / ".local" / "hermes" / "model" / "runs" / "run" / "workspaces" / "task"
    workspace.mkdir(parents=True)
    visible = workspace / "visible.txt"
    visible.write_text("workspace-visible", encoding="utf-8")
    secret = repo / "golden-secret.txt"
    secret.write_text("must-not-leak", encoding="utf-8")
    monkeypatch.setattr("core.benchmark.sandbox.REPO_ROOT", repo)

    plan = workspace_sandbox("hermes", workspace, "required")
    command = plan.wrap([
        "/bin/sh",
        "-c",
        (
            f"test \"$(cat {visible})\" = workspace-visible && "
            f"test ! -e {secret} && "
            "printf sandbox-write > created-inside.txt"
        ),
    ])
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)

    assert completed.returncode == 0, completed.stderr
    assert (workspace / "created-inside.txt").read_text(encoding="utf-8") == "sandbox-write"
    assert secret.read_text(encoding="utf-8") == "must-not-leak"


def test_local_harness_does_not_use_grader_blacklist(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = repo / "results" / ".local" / "hermes" / "model" / "runs" / "run" / "workspaces" / "task"
    workspace.mkdir(parents=True)
    monkeypatch.setattr("core.benchmark.sandbox.REPO_ROOT", repo)
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    monkeypatch.setattr(
        "core.benchmark.sandbox._benchmark_owned_paths",
        lambda workspace: (_ for _ in ()).throw(AssertionError("blacklist must not be consulted")),
    )

    command = workspace_sandbox("hermes", workspace, "required").wrap(["hermes"])

    assert _has_sequence(command, ["--tmpfs", str(repo.resolve())])


def test_agentzero_transport_masks_golden_and_benchmark_content(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    package = repo / "core" / "benchmark"
    package.mkdir(parents=True)
    workspace = repo / "results" / ".local" / "agentzero" / "model" / "runs" / "run" / "workspaces" / "task"
    workspace.mkdir(parents=True)
    (repo / "benchmarks").mkdir()
    (repo / "tests").mkdir()
    (repo / "docs").mkdir()
    (repo / "results" / "summary.json").parent.mkdir(parents=True, exist_ok=True)
    (repo / "results" / "summary.json").write_text("{}", encoding="utf-8")
    (package / "golden_solutions.py").write_text("secret", encoding="utf-8")
    (package / "parametric_goldens.py").write_text("secret", encoding="utf-8")
    (package / "reference_checks.py").write_text("secret", encoding="utf-8")
    monkeypatch.setattr("core.benchmark.sandbox.REPO_ROOT", repo)
    monkeypatch.setattr("core.benchmark.sandbox.BENCHMARK_PACKAGE_ROOT", package)
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")

    plan = workspace_sandbox("agentzero", workspace, "required")
    command = plan.wrap(["python", "-m", "core.benchmark.agentzero_client", "prompt"])

    assert plan.strategy == "bubblewrap_remote_transport_grader_hidden"
    assert _has_sequence(command, ["--tmpfs", str((repo / "benchmarks").resolve())])
    assert _has_sequence(command, ["--tmpfs", str((repo / "tests").resolve())])
    assert _has_sequence(command, ["--tmpfs", str((repo / "docs").resolve())])
    assert _has_sequence(command, ["--tmpfs", str((repo / "results").resolve())])
    assert _has_sequence(command, ["--ro-bind", "/dev/null", str((package / "golden_solutions.py").resolve())])
    assert _has_sequence(command, ["--ro-bind", "/dev/null", str((package / "parametric_goldens.py").resolve())])
    assert _has_sequence(command, ["--ro-bind", "/dev/null", str((package / "reference_checks.py").resolve())])


def test_historical_results_sibling_workspaces_and_oracles_are_hidden(tmp_path: Path):
    local = tmp_path / "results" / ".local"
    workspace = local / "piagent" / "ornith" / "runs" / "run-2" / "workspaces" / "task-2"
    workspace.mkdir(parents=True)
    other_harness = local / "hermes"; (other_harness / "m" / "runs" / "r").mkdir(parents=True)
    other_model = local / "piagent" / "old-model"; (other_model / "runs" / "r").mkdir(parents=True)
    other_run = local / "piagent" / "ornith" / "runs" / "run-1"; other_run.mkdir(parents=True)
    sibling = workspace.parent / "task-1"; sibling.mkdir()
    run_dir = workspace.parent.parent
    logs = run_dir / "logs"; logs.mkdir()
    oracles = run_dir / "oracles"; oracles.mkdir()
    (oracles / "task-2.json").write_text('{"secret": true}', encoding="utf-8")
    metadata = run_dir / "run.json"; metadata.write_text("{}", encoding="utf-8")
    directories, files = _result_history_paths(workspace)
    assert other_harness in directories
    assert other_model in directories
    assert other_run in directories
    assert sibling in directories
    assert logs in directories
    assert oracles in directories
    assert metadata in files
    assert workspace not in directories


def test_sensitive_path_registry_includes_golden_material(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    package = repo / "core" / "benchmark"
    workspace = repo / "results" / ".local" / "agentzero" / "m" / "runs" / "r" / "workspaces" / "t"
    workspace.mkdir(parents=True)
    package.mkdir(parents=True)
    (package / "golden_solutions.py").write_text("secret", encoding="utf-8")
    (package / "parametric_goldens.py").write_text("secret", encoding="utf-8")
    monkeypatch.setattr("core.benchmark.sandbox.REPO_ROOT", repo)
    monkeypatch.setattr("core.benchmark.sandbox.BENCHMARK_PACKAGE_ROOT", package)

    _, files = _benchmark_owned_paths(workspace)

    assert package / "golden_solutions.py" in files
    assert package / "parametric_goldens.py" in files


def test_pi_state_writes_use_an_ephemeral_overlay(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = repo / "results" / ".local" / "piagent" / "m" / "runs" / "r" / "workspaces" / "t"
    workspace.mkdir(parents=True)
    pi_state = tmp_path / ".pi" / "agent"; pi_state.mkdir(parents=True)
    monkeypatch.setattr("core.benchmark.sandbox.REPO_ROOT", repo)
    monkeypatch.setattr("core.benchmark.sandbox.Path.home", lambda: tmp_path)
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    command = workspace_sandbox("piagent", workspace, "required").wrap(["pi"])
    assert _has_sequence(command, ["--overlay-src", str(pi_state), "--tmp-overlay", str(pi_state)])


def test_other_harnesses_do_not_expose_pi_state(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    workspace = repo / "results" / ".local" / "hermes" / "m" / "runs" / "r" / "workspaces" / "t"
    workspace.mkdir(parents=True)
    pi_state = tmp_path / ".pi" / "agent"; pi_state.mkdir(parents=True)
    monkeypatch.setattr("core.benchmark.sandbox.REPO_ROOT", repo)
    monkeypatch.setattr("core.benchmark.sandbox.Path.home", lambda: tmp_path)
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    command = workspace_sandbox("hermes", workspace, "required").wrap(["hermes"])
    assert "--tmp-overlay" not in command


def test_required_sandbox_fails_closed(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="required"):
        workspace_sandbox("hermes", tmp_path, "required")


def test_auto_records_unconfined_fallback(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: None)
    plan = workspace_sandbox("hermes", tmp_path, "auto")
    assert plan.strategy == "cwd_only_unconfined"
    assert plan.write_confined is False
    assert plan.grader_hidden is False
