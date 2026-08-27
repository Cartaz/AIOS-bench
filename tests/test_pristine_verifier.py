from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core.benchmark.pristine_verifier import run_pristine_verifier


def test_unconfined_fallback_is_explicit_and_uses_isolated_python(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.benchmark.pristine_verifier.shutil.which", lambda name: None)

    result = run_pristine_verifier(
        tmp_path,
        "Path('result.txt').write_text('ok', encoding='utf-8')",
        mode="auto",
    )

    assert result.returncode == 0, result.stderr
    assert result.isolation_strategy == "isolated_python_unconfined"
    assert result.filesystem_confined is False
    assert result.network_confined is False
    assert (tmp_path / "result.txt").read_text(encoding="utf-8") == "ok"


def test_required_verifier_sandbox_fails_closed_without_bubblewrap(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.benchmark.pristine_verifier.shutil.which", lambda name: None)

    with pytest.raises(RuntimeError, match="required"):
        run_pristine_verifier(tmp_path, "pass", mode="required")


def test_bubblewrap_plan_reports_filesystem_and_network_confinement(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Completed()

    monkeypatch.setattr("core.benchmark.pristine_verifier.shutil.which", lambda name: "/usr/bin/bwrap")
    monkeypatch.setattr("core.benchmark.pristine_verifier.subprocess.run", fake_run)

    result = run_pristine_verifier(tmp_path, "print('ok')", mode="required")

    command = captured["command"]
    assert isinstance(command, list)
    assert "--unshare-net" in command
    assert "--bind" in command
    assert str(tmp_path.resolve()) in command
    assert "/workspace" in command
    assert command[-4:-1] == ["-I", "-S", "-c"]
    assert result.isolation_strategy == "bubblewrap_minimal_runtime"
    assert result.filesystem_confined is True
    assert result.network_confined is True


def test_real_bubblewrap_verifier_cannot_read_external_secret(tmp_path: Path) -> None:
    if shutil.which("bwrap") is None:
        pytest.skip("bubblewrap is unavailable")

    pristine = tmp_path / "pristine"
    pristine.mkdir()
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("must-not-leak", encoding="utf-8")
    code = (
        "secret = Path(" + repr(str(secret)) + ")\n"
        "assert not secret.exists()\n"
        "Path('inside.txt').write_text('verified', encoding='utf-8')\n"
    )

    result = run_pristine_verifier(pristine, code, mode="required")

    assert result.returncode == 0, result.stderr
    assert (pristine / "inside.txt").read_text(encoding="utf-8") == "verified"
    assert secret.read_text(encoding="utf-8") == "must-not-leak"
