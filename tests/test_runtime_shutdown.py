from __future__ import annotations

from core.cancellation import CancellationToken
from ui.runtime import DesktopRuntime, SHUTDOWN_WAIT_MS


class _Controller:
    pass


class _Thread:
    def __init__(self, running: bool = True, wait_result: bool = True) -> None:
        self.running = running
        self.wait_result = wait_result
        self.wait_calls: list[int] = []

    def isRunning(self) -> bool:
        return self.running

    def wait(self, timeout: int) -> bool:
        self.wait_calls.append(timeout)
        return self.wait_result


def test_shutdown_cancels_benchmark_and_waits_bounded() -> None:
    runtime = DesktopRuntime(_Controller())
    thread = _Thread()
    token = CancellationToken()
    runtime._thread = thread
    runtime._operation = "benchmark"
    runtime._cancellation_token = token

    runtime.shutdown()

    assert token.is_cancelled is True
    assert thread.wait_calls == [SHUTDOWN_WAIT_MS]


def test_shutdown_cancels_doctor_install_and_waits_bounded() -> None:
    runtime = DesktopRuntime(_Controller())
    thread = _Thread()
    token = CancellationToken()
    runtime._thread = thread
    runtime._operation = "doctor_install"
    runtime._cancellation_token = token

    runtime.shutdown()

    assert token.is_cancelled is True
    assert thread.wait_calls == [SHUTDOWN_WAIT_MS]


def test_shutdown_still_waits_when_operation_has_no_token() -> None:
    runtime = DesktopRuntime(_Controller())
    thread = _Thread()
    runtime._thread = thread
    runtime._operation = "legacy_operation"

    runtime.shutdown()

    assert thread.wait_calls == [SHUTDOWN_WAIT_MS]


def test_shutdown_is_idempotent_when_idle() -> None:
    runtime = DesktopRuntime(_Controller())
    runtime.shutdown()
    runtime.shutdown()
