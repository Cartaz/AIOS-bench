from __future__ import annotations

from pathlib import Path

from core.benchmark import managed_runtimes
from core.benchmark.processes import OwnedProcessOutcome


def test_requested_node_version_uses_pinned_default_and_explicit_override(monkeypatch):
    monkeypatch.delenv("AIOS_BENCH_NODE_VERSION", raising=False)
    assert managed_runtimes.requested_node_version() == "24.20.0"
    monkeypatch.setenv("AIOS_BENCH_NODE_VERSION", "22.23.2")
    assert managed_runtimes.requested_node_version() == "22.23.2"


def test_install_managed_harness_uses_project_npm_prefix(monkeypatch, tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    npm = bin_dir / "npm"
    npm.write_text("", encoding="utf-8")
    npm.chmod(0o755)
    executable = bin_dir / "pi"
    calls: list[tuple[list[str], dict]] = []

    monkeypatch.setattr(managed_runtimes, "PROJECT_BIN", bin_dir)
    monkeypatch.setattr(managed_runtimes, "PROJECT_VENV", tmp_path)
    monkeypatch.setattr(managed_runtimes, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        managed_runtimes,
        "npm_environment",
        lambda: {"PATH": str(bin_dir), "NPM_CONFIG_PREFIX": str(tmp_path)},
    )

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        executable.write_text("", encoding="utf-8")
        executable.chmod(0o755)
        return OwnedProcessOutcome(0)

    monkeypatch.setattr(managed_runtimes, "run_owned", fake_run)
    result = managed_runtimes.install_managed_harness("piagent", ensure_node=False)

    assert result == executable
    assert calls[0][0] == [
        str(npm),
        "install",
        "-g",
        "--ignore-scripts",
        "@earendil-works/pi-coding-agent@0.84.4",
    ]
    assert calls[0][1]["env"]["NPM_CONFIG_PREFIX"] == str(tmp_path)


def test_ensure_project_node_repairs_mismatched_local_runtime(monkeypatch, tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    node = bin_dir / "node"
    node.write_text("old", encoding="utf-8")
    node.chmod(0o755)
    observed: list[list[str]] = []
    versions = iter(["v22.18.0", "v24.20.0"])

    monkeypatch.setattr(managed_runtimes, "PROJECT_BIN", bin_dir)
    monkeypatch.setattr(managed_runtimes, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("AIOS_BENCH_NODE_VERSION", raising=False)
    monkeypatch.setattr(managed_runtimes, "_first_output_line", lambda command: next(versions))

    def fake_run(command, **kwargs):
        observed.append(command)
        return OwnedProcessOutcome(0)

    monkeypatch.setattr(managed_runtimes, "run_owned", fake_run)

    assert managed_runtimes.ensure_project_node() == "v24.20.0"
    assert observed
    assert "-m" in observed[0]
    assert "nodeenv" in observed[0]
    assert "--node=24.20.0" in observed[0]
    assert "--force" in observed[0]
