from pathlib import Path

import pytest

from core.benchmark.sandbox import _result_history_paths, workspace_sandbox


def _has_sequence(command: list[str], sequence: list[str]) -> bool:
    width = len(sequence)
    return any(command[index:index + width] == sequence for index in range(len(command) - width + 1))


def test_bubblewrap_confines_writes_to_workspace(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    monkeypatch.setattr("core.benchmark.sandbox._benchmark_owned_paths", lambda workspace: ([], []))
    plan = workspace_sandbox("piagent", tmp_path, "required")
    command = plan.wrap(["pi", "--mode", "rpc"])
    assert plan.strategy == "bubblewrap_readonly_root"
    assert _has_sequence(command, ["--ro-bind", "/", "/"])
    assert _has_sequence(command, ["--bind", str(tmp_path.resolve()), str(tmp_path.resolve())])
    assert command[-3:] == ["pi", "--mode", "rpc"]


def test_bubblewrap_masks_benchmark_owned_grader_paths(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    hidden_dir = tmp_path / "benchmarks"; hidden_dir.mkdir()
    hidden_file = tmp_path / "reference_checks.py"; hidden_file.write_text("secret", encoding="utf-8")
    monkeypatch.setattr("core.benchmark.sandbox._benchmark_owned_paths", lambda workspace: ([hidden_dir], [hidden_file]))
    workspace = tmp_path / "workspace"; workspace.mkdir()
    plan = workspace_sandbox("hermes", workspace, "required")
    command = plan.wrap(["hermes"])
    assert plan.strategy == "bubblewrap_readonly_root_grader_hidden"
    assert plan.grader_hidden is True
    assert _has_sequence(command, ["--tmpfs", str(hidden_dir.resolve())])
    assert _has_sequence(command, ["--ro-bind", "/dev/null", str(hidden_file.resolve())])


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


def test_bubblewrap_masks_current_parametric_oracle_directory(monkeypatch, tmp_path: Path):
    local = tmp_path / "results" / ".local"
    workspace = local / "piagent" / "ornith" / "runs" / "run-2" / "workspaces" / "task-2"
    workspace.mkdir(parents=True)
    oracles = workspace.parent.parent / "oracles"
    oracles.mkdir()
    (oracles / "task-2.json").write_text('{"secret": true}', encoding="utf-8")
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")

    command = workspace_sandbox("hermes", workspace, "required").wrap(["hermes"])

    assert _has_sequence(command, ["--tmpfs", str(oracles.resolve())])


def test_pi_state_writes_use_an_ephemeral_overlay(monkeypatch, tmp_path: Path):
    pi_state = tmp_path / ".pi" / "agent"; pi_state.mkdir(parents=True)
    monkeypatch.setattr("core.benchmark.sandbox.Path.home", lambda: tmp_path)
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    monkeypatch.setattr("core.benchmark.sandbox._benchmark_owned_paths", lambda workspace: ([], []))
    command = workspace_sandbox("piagent", tmp_path / "workspace", "required").wrap(["pi"])
    assert _has_sequence(command, ["--overlay-src", str(pi_state), "--tmp-overlay", str(pi_state)])


def test_other_harnesses_do_not_expose_pi_state(monkeypatch, tmp_path: Path):
    pi_state = tmp_path / ".pi" / "agent"; pi_state.mkdir(parents=True)
    monkeypatch.setattr("core.benchmark.sandbox.Path.home", lambda: tmp_path)
    monkeypatch.setattr("core.benchmark.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    monkeypatch.setattr("core.benchmark.sandbox._benchmark_owned_paths", lambda workspace: ([], []))
    command = workspace_sandbox("hermes", tmp_path / "workspace", "required").wrap(["hermes"])
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
