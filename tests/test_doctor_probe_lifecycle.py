from __future__ import annotations

import subprocess

from core.benchmark import doctor


class _Process:
    def communicate(self, timeout: float):
        assert timeout == 4
        raise subprocess.TimeoutExpired(["tool", "--version"], timeout)


def test_doctor_probe_timeout_uses_owned_process_cleanup(monkeypatch) -> None:
    process = _Process()
    cleaned: list[object] = []
    monkeypatch.setattr(doctor.shutil, "which", lambda executable: f"/bin/{executable}")
    monkeypatch.setattr(doctor, "spawn_owned", lambda *args, **kwargs: process)
    monkeypatch.setattr(doctor, "terminate_owned", lambda value: cleaned.append(value))

    installed, path, version = doctor._probe("tool")

    assert installed is True
    assert path == "/bin/tool"
    assert version is None
    assert cleaned == [process]
