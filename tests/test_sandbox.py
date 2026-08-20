from pathlib import Path

import pytest

from aios_bench.sandbox import workspace_sandbox


def test_bubblewrap_confines_writes_to_workspace(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    plan = workspace_sandbox("piagent", tmp_path, "required")
    command = plan.wrap(["pi", "--mode", "rpc"])
    assert plan.strategy == "bubblewrap_readonly_root"
    assert ["--ro-bind", "/", "/"] == command[3:6]
    assert "--bind" in command
    assert str(tmp_path.resolve()) in command
    assert command[-3:] == ["pi", "--mode", "rpc"]


def test_pi_state_writes_use_an_ephemeral_overlay(monkeypatch, tmp_path: Path):
    pi_state = tmp_path / ".pi" / "agent"
    pi_state.mkdir(parents=True)
    monkeypatch.setattr("aios_bench.sandbox.Path.home", lambda: tmp_path)
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")

    command = workspace_sandbox("piagent", tmp_path / "workspace", "required").wrap(["pi"])

    assert ["--overlay-src", str(pi_state), "--tmp-overlay", str(pi_state)] == command[8:12]


def test_opencode_state_writes_use_ephemeral_overlays(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr("aios_bench.sandbox.Path.home", lambda: tmp_path)
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")
    state_dirs = [
        tmp_path / ".local" / "share" / "opencode",
        tmp_path / ".config" / "opencode",
        tmp_path / ".cache" / "opencode",
    ]
    for path in state_dirs:
        path.mkdir(parents=True)

    command = workspace_sandbox("opencode", tmp_path / "workspace", "required").wrap(["opencode"])

    for path in state_dirs:
        state = str(path.resolve())
        assert ["--overlay-src", state, "--tmp-overlay", state] in [
            command[index:index + 4] for index in range(len(command) - 3)
        ]


def test_other_harnesses_do_not_expose_pi_state(monkeypatch, tmp_path: Path):
    pi_state = tmp_path / ".pi" / "agent"
    pi_state.mkdir(parents=True)
    monkeypatch.setattr("aios_bench.sandbox.Path.home", lambda: tmp_path)
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda name: "/usr/bin/bwrap")

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
