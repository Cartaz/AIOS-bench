from __future__ import annotations

import os
from pathlib import Path

from core.benchmark import runtime_paths


def test_resolve_executable_prefers_project_bin(monkeypatch, tmp_path: Path):
    executable = tmp_path / "node"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setattr(runtime_paths, "PROJECT_BIN", tmp_path)
    monkeypatch.setattr(runtime_paths.shutil, "which", lambda name: f"/system/{name}")

    assert runtime_paths.resolve_executable("node") == str(executable)


def test_with_project_bin_preserves_restricted_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(runtime_paths, "PROJECT_BIN", tmp_path)
    monkeypatch.setenv("SECRET_PARENT_VALUE", "must-not-leak")

    environment = runtime_paths.with_project_bin({"ONLY_THIS": "1", "PATH": "/usr/bin"})

    assert environment["ONLY_THIS"] == "1"
    assert environment["PATH"].split(os.pathsep)[0] == str(tmp_path)
    assert "SECRET_PARENT_VALUE" not in environment


def test_npm_environment_uses_project_venv(monkeypatch, tmp_path: Path):
    venv = tmp_path / ".venv"
    bin_dir = venv / "bin"
    monkeypatch.setattr(runtime_paths, "PROJECT_VENV", venv)
    monkeypatch.setattr(runtime_paths, "PROJECT_BIN", bin_dir)

    environment = runtime_paths.npm_environment({"PATH": "/usr/bin"})

    assert environment["NPM_CONFIG_PREFIX"] == str(venv)
    assert environment["PATH"].split(os.pathsep)[0] == str(bin_dir)
