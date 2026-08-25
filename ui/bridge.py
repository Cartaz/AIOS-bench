from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from core.app_controller import AppController


class Bridge(QObject):
    catalogChanged = Signal(str)
    runStateChanged = Signal(str)
    progressChanged = Signal(str)
    errorOccurred = Signal(str)
    runFinished = Signal(str)

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self._controller = controller
        controller.catalog_changed.connect(self.catalogChanged)
        controller.run_state_changed.connect(self.runStateChanged)
        controller.progress_changed.connect(self.progressChanged)
        controller.error_occurred.connect(self.errorOccurred)
        controller.run_finished.connect(self.runFinished)

    @Slot(str, result=str)
    def getCatalog(self, suite: str) -> str:
        try:
            return self._controller.catalog_json(suite or "frontier_v3")
        except (ValueError, OSError) as exc:
            self.errorOccurred.emit(str(exc))
            return "{}"

    @Slot(str, result=bool)
    def startRun(self, payload: str) -> bool:
        try:
            self._controller.start_run(payload)
        except (TypeError, ValueError, RuntimeError) as exc:
            self.errorOccurred.emit(str(exc))
            return False
        return True
