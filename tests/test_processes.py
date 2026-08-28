from __future__ import annotations

import signal
import subprocess

from core.benchmark import processes


class FakeProcess:
    def __init__(self, pid: int = 4321, *, running: bool = True) -> None:
        self.pid = pid
        self.returncode = None if running else 0
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls: list[float | None] = []

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        self.returncode = 0
        return 0

    def terminate(self):
        self.terminate_calls += 1

    def kill(self):
        self.kill_calls += 1
        self.returncode = -9


def test_spawn_owned_creates_posix_session(monkeypatch):
    captured = {}
    fake = FakeProcess()

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return fake

    monkeypatch.setattr(processes.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(processes.os, "name", "posix")

    result = processes.spawn_owned(["agent", "--run"], cwd="/tmp")

    assert result is fake
    assert captured["kwargs"]["start_new_session"] is True
    assert getattr(fake, "_aios_process_group") == fake.pid


def test_terminate_owned_clears_group_even_if_parent_already_exited(monkeypatch):
    fake = FakeProcess(running=False)
    setattr(fake, "_aios_process_group", fake.pid)
    signals = []
    monkeypatch.setattr(processes.os, "name", "posix")
    monkeypatch.setattr(processes.os, "killpg", lambda group, sig: signals.append((group, sig)))

    processes.terminate_owned(fake, grace_seconds=0.01)

    assert signals == [(fake.pid, signal.SIGKILL)]
    assert getattr(fake, "_aios_cleanup_done") is True


def test_terminate_owned_uses_term_then_group_kill(monkeypatch):
    fake = FakeProcess(running=True)
    setattr(fake, "_aios_process_group", fake.pid)
    signals = []
    monkeypatch.setattr(processes.os, "name", "posix")
    monkeypatch.setattr(processes.os, "killpg", lambda group, sig: signals.append((group, sig)))

    processes.terminate_owned(fake, grace_seconds=0.01)

    assert signals == [
        (fake.pid, signal.SIGTERM),
        (fake.pid, signal.SIGKILL),
    ]
    assert fake.wait_calls == [0.01]


def test_terminate_owned_is_idempotent(monkeypatch):
    fake = FakeProcess(running=False)
    setattr(fake, "_aios_process_group", fake.pid)
    signals = []
    monkeypatch.setattr(processes.os, "name", "posix")
    monkeypatch.setattr(processes.os, "killpg", lambda group, sig: signals.append((group, sig)))

    processes.terminate_owned(fake)
    processes.terminate_owned(fake)

    assert signals == [(fake.pid, signal.SIGKILL)]


def test_non_posix_fallback_kills_after_grace_timeout(monkeypatch):
    fake = FakeProcess(running=True)

    def timeout_wait(timeout=None):
        fake.wait_calls.append(timeout)
        if fake.kill_calls == 0:
            raise subprocess.TimeoutExpired("agent", timeout)
        fake.returncode = -9
        return -9

    fake.wait = timeout_wait
    monkeypatch.setattr(processes.os, "name", "nt")

    processes.terminate_owned(fake, grace_seconds=0.01)

    assert fake.terminate_calls == 1
    assert fake.kill_calls == 1
    assert fake.wait_calls == [0.01, 0.01]
