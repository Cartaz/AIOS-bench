from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_install_script_repairs_incompatible_virtualenv() -> None:
    source = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "venv_is_compatible" in source
    assert ".venv/bin/python" in source
    assert "sys.version_info >= (3, 12)" in source
    assert "rm -rf .venv" in source
    assert '"$PYTHON_BIN" -m venv .venv' in source


def test_install_script_verifies_virtualenv_python_after_creation() -> None:
    source = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "[ERROR] .venv uses unsupported Python" in source
