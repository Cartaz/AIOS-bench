from __future__ import annotations

from pathlib import Path

from core.benchmark.managed_runtimes import DEFAULT_NODE_VERSION, MANAGED_HARNESSES

ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "install.sh").read_text(encoding="utf-8")


def test_install_script_repairs_incompatible_virtualenv() -> None:
    source = _source()
    assert "venv_is_compatible" in source
    assert 'VENV_DIR="$ROOT_DIR/.venv"' in source
    assert "sys.version_info >= (3, 12)" in source
    assert 'rm -rf "$VENV_DIR"' in source
    assert '"$PYTHON_BIN" -m venv "$VENV_DIR"' in source


def test_install_script_verifies_virtualenv_python_after_creation() -> None:
    source = _source()
    assert "[ERROR] .venv uses unsupported Python" in source


def test_install_script_delegates_managed_bootstrap_to_python_owner() -> None:
    source = _source()
    assert "AIOS_BENCH_SKIP_MANAGED_HARNESSES" in source
    assert '"$VENV_BIN/python" -m core.benchmark.managed_runtimes' in source
    assert "npm install" not in source
    assert "nodeenv" not in source


def test_managed_runtime_versions_are_explicitly_pinned() -> None:
    assert DEFAULT_NODE_VERSION == "24.20.0"
    assert [(item.name, item.package, item.executable) for item in MANAGED_HARNESSES] == [
        ("piagent", "@earendil-works/pi-coding-agent@0.84.4", "pi"),
        ("opencode", "opencode-ai@1.18.26", "opencode"),
        ("letta", "@letta-ai/letta-code@0.31.11", "letta"),
        ("claude", "@anthropic-ai/claude-code@2.1.236", "claude"),
        ("deepseek", "@deepseek-ai/dsh@0.1.2-alpha.5", "dsh"),
    ]


def test_install_script_does_not_silently_install_external_harnesses() -> None:
    source = _source()
    assert "curl -fsSL" not in source
    assert "sudo " not in source
    assert "docker run" not in source.lower()
    assert "Hermes Agent" in source
    assert "Goose" in source
    assert "Agent Zero" in source
