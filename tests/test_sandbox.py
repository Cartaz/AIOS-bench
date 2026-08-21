from pathlib import Path

import pytest

from aios_bench.sandbox import workspace_sandbox


def _has_sequence(command: list[str], sequence: list[str]) -> bool:
    width = len(sequence)
    return any(command[index:index + width] == sequence for index in range(len(command) - width + 1))


def test_codex_legacy_adapter_keeps_its_managed_sandbox(tmp_path: Path):
    plan = workspace_sandbox("codex", tmp_path, "required")
    assert plan.strategy == "adapter_workspace_write"
    assert plan.write_confined is True
    assert plan.grader_hidden is False
    assert plan.wrap(["codex"]) == ["codex"]


def test_bubblewrap_confines_writes_to_workspace(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    monkeypatch.setattr("aios_bench.sandbox._benchmark_owned_paths", lambda: ([], []))
    plan = workspace_sandbox("piagent", tmp_path, "required")
    command = plan.wrap(["pi", "--mode", "rpc"])
    assert plan.strategy == "bubblewrap_readonly_root"
    assert _has_sequence(command, ["--ro-bind", "/", "/"])
    assert _has_sequence(command, ["--bind", str(tmp_path.resolve()), str(tmp_path.resolve())])
    assert command[-3:] == ["pi", "--mode", "rpc"]


def test_bubblewrap_masks_benchmark_owned_grader_paths(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    hidden_dir = tmp_path / "benchmarks"; hidden_dir.mkdir()
    hidden_file = tmp_path / "reference_checks.py"; hidden_file.write_text("secret", encoding="utf-8")
    monkeypatch.setattr("aios_bench.sandbox._benchmark_owned_paths", lambda: ([hidden_dir], [hidden_file]))
    workspace = tmp_path / "workspace"; workspace.mkdir()
    plan = workspace_sandbox("hermes", workspace, "required")
    command = plan.wrap(["hermes"])
    assert plan.strategy == "bubblewrap_readonly_root_grader_hidden"
    assert plan.grader_hidden is True
    assert _has_sequence(command, ["--tmpfs", str(hidden_dir.resolve())])
    assert _has_sequence(command, ["--ro-bind", "/dev/null", str(hidden_file.resolve())])


def test_pi_state_writes_use_an_ephemeral_overlay(monkeypatch, tmp_path: Path):
    pi_state = tmp_path / ".pi" / "agent"; pi_state.mkdir(parents=True)
    monkeypatch.setattr("aios_bench.sandbox.Path.home", lambda: tmp_path)
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    monkeypatch.setattr("aios_bench.sandbox._benchmark_owned_paths", lambda: ([], []))
    command = workspace_sandbox("piagent", tmp_path / "workspace", "required").wrap(["pi"])
    assert _has_sequence(command, ["--overlay-src", str(pi_state), "--tmp-overlay", str(pi_state)])


def test_other_harnesses_do_not_expose_pi_state(monkeypatch, tmp_path: Path):
    pi_state = tmp_path / ".pi" / "agent"; pi_state.mkdir(parents=True)
    monkeypatch.setattr("aios_bench.sandbox.Path.home", lambda: tmp_path)
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    monkeypatch.setattr("aios_bench.sandbox._benchmark_owned_paths", lambda: ([], []))
    command = workspace_sandbox("hermes", tmp_path / "workspace", "required").wrap(["hermes"])
    assert "--tmp-overlay" not in command


def test_required_sandbox_fails_closed(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="required"):
        workspace_sandbox("hermes", tmp_path, "required")


def test_auto_records_unconfined_fallback(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: None)
    plan = workspace_sandbox("hermes", tmp_path, "auto")
    assert plan.strategy == "cwd_only_unconfined"
    assert plan.write_confined is False
    assert plan.grader_hidden is False
