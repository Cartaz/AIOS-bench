from __future__ import annotations

import threading

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtTest import QTest

from ui.runtime import DesktopRuntime


class _Controller:
    def __init__(self) -> None:
        self.inspect_thread: int | None = None
        self.install_thread: int | None = None

    def doctor_json(self, cancellation_check=None) -> str:
        assert cancellation_check is not None
        assert cancellation_check() is False
        self.inspect_thread = threading.get_ident()
        return '{"report":{"harnesses":[]},"profile":{}}'

    def validate_install_harness(self, name: str) -> None:
        assert name == "piagent"

    def install_harness(self, name: str, cancellation_check=None) -> str:
        assert name == "piagent"
        assert cancellation_check is not None
        self.install_thread = threading.get_ident()
        return '{"report":{"harnesses":[]},"profile":{}}'


def _wait_for_doctor(runtime: DesktopRuntime, start) -> str:
    loop = QEventLoop()
    values: list[str] = []
    runtime.doctorChanged.connect(lambda value: (values.append(value), loop.quit()))
    start()
    QTimer.singleShot(3000, loop.quit)
    loop.exec()
    waited = 0
    while runtime.is_busy and waited < 3000:
        QTest.qWait(20)
        waited += 20
    return values[-1] if values else ""


def test_doctor_inspection_runs_off_gui_thread() -> None:
    QCoreApplication.instance() or QCoreApplication([])
    controller = _Controller()
    runtime = DesktopRuntime(controller)
    gui_thread = threading.get_ident()

    result = _wait_for_doctor(runtime, runtime.inspect_doctor)

    assert '"report"' in result
    assert controller.inspect_thread is not None
    assert controller.inspect_thread != gui_thread
    runtime.shutdown()


def test_post_install_inspection_payload_is_produced_in_worker() -> None:
    QCoreApplication.instance() or QCoreApplication([])
    controller = _Controller()
    runtime = DesktopRuntime(controller)
    gui_thread = threading.get_ident()

    result = _wait_for_doctor(runtime, lambda: runtime.install_harness("piagent"))

    assert '"report"' in result
    assert controller.install_thread is not None
    assert controller.install_thread != gui_thread
    runtime.shutdown()
