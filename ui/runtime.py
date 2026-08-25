from __future__ import annotations

import json
import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot

from core.app_controller import AppController
from core.cancellation import CancellationToken

logger = logging.getLogger(__name__)


class BackgroundWorker(QObject):
    event = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[Callable[[dict[str, object]], None]], object]) -> None:
        super().__init__()
        self._operation = operation

    @Slot()
    def run(self) -> None:
        try:
            result = self._operation(self.event.emit)
        except Exception:
            logger.exception("Background desktop operation failed")
            self.failed.emit("Operation failed. See application log for details.")
        else:
            self.finished.emit(result)


class DesktopRuntime(QObject):
    """Owns Qt worker lifecycle and translates long-running core work into signals."""

    doctorChanged = Signal(str)
    runStateChanged = Signal(str)
    progressChanged = Signal(str)
    errorOccurred = Signal(str)
    runFinished = Signal(str)

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self._controller = controller
        self._thread: QThread | None = None
        self._worker: BackgroundWorker | None = None
        self._operation: str | None = None
        self._cancellation_token: CancellationToken | None = None

    @property
    def is_busy(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    @property
    def is_running(self) -> bool:
        return self._operation == "benchmark" and self.is_busy

    def start_run(self, payload: str) -> None:
        request = self._controller.prepare_run(payload)
        token = CancellationToken()
        self._cancellation_token = token
        self._start(
            "benchmark",
            lambda emit: self._controller.run_benchmark(request, emit, token),
        )

    def cancel_run(self) -> bool:
        if not self.is_running or self._cancellation_token is None:
            return False
        self._cancellation_token.cancel()
        self.runStateChanged.emit(
            json.dumps({"running": True, "busy": True, "operation": "benchmark", "cancelling": True})
        )
        return True

    def install_harness(self, name: str) -> None:
        harness = name.strip()
        self._controller.validate_install_harness(harness)
        self._start(
            "doctor_install",
            lambda _emit: self._controller.install_harness(harness),
        )

    def _start(
        self,
        operation: str,
        callback: Callable[[Callable[[dict[str, object]], None]], object],
    ) -> None:
        if self.is_busy:
            raise RuntimeError("Another background operation is already active")

        thread = QThread(self)
        worker = BackgroundWorker(callback)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.event.connect(self._on_event)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        self._operation = operation
        self.runStateChanged.emit(
            json.dumps({"running": operation == "benchmark", "busy": True, "operation": operation})
        )
        thread.start()

    @Slot(object)
    def _on_event(self, event: object) -> None:
        if self._operation == "benchmark":
            self.progressChanged.emit(json.dumps(event, ensure_ascii=False))

    @Slot(object)
    def _on_finished(self, result: object) -> None:
        if self._operation == "benchmark":
            self.runFinished.emit(json.dumps(result, ensure_ascii=False))
        elif self._operation == "doctor_install":
            self.doctorChanged.emit(self._controller.doctor_json())

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.errorOccurred.emit(message)

    @Slot()
    def _thread_finished(self) -> None:
        self._worker = None
        self._thread = None
        self._operation = None
        self._cancellation_token = None
        self.runStateChanged.emit(
            json.dumps({"running": False, "busy": False, "operation": None, "cancelling": False})
        )

    def shutdown(self) -> None:
        if self.is_running:
            self.cancel_run()
            logger.info("Shutdown requested; benchmark cancellation signalled")
        elif self.is_busy:
            logger.warning("Shutdown requested while a non-benchmark operation is active")
