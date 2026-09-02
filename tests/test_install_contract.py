from __future__ import annotations

from pathlib import Path

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


def test_install_script_bootstraps_project_local_node_and_managed_harnesses() -> None:
    source = _source()
    assert 'NODE_VERSION="${AIOS_BENCH_NODE_VERSION:-24.20.0}"' in source
    assert "AIOS_BENCH_SKIP_MANAGED_HARNESSES" in source
    assert '"$VENV_BIN/nodeenv" -p --node="$NODE_VERSION" --prebuilt' in source
    assert 'NPM_CONFIG_PREFIX="$VENV_DIR"' in source
    for package in (
        "@mariozechner/pi-coding-agent",
        "opencode-ai",
        "@letta-ai/letta-code",
        "@anthropic-ai/claude-code",
        "@deepseek-ai/dsh@0.1.2-alpha.5",
    ):
        assert package in source


def test_install_script_does_not_silently_install_external_harnesses() -> None:
    source = _source()
    assert "curl -fsSL" not in source
    assert "sudo " not in source
    assert "docker run" not in source.lower()
    assert "Hermes Agent" in source
    assert "Goose" in source
    assert "Agent Zero" in source
