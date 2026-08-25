from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from core.app_controller import AppController
from .runtime import DesktopRuntime


class Bridge(QObject):
    catalogChanged = Signal(str)
    doctorChanged = Signal(str)
    runStateChanged = Signal(str)
    progressChanged = Signal(str)
    errorOccurred = Signal(str)
    runFinished = Signal(str)

    def __init__(self, controller: AppController, runtime: DesktopRuntime) -> None:
        super().__init__()
        self._controller = controller
        self._runtime = runtime
        runtime.doctorChanged.connect(self.doctorChanged)
        runtime.runStateChanged.connect(self.runStateChanged)
        runtime.progressChanged.connect(self.progressChanged)
        runtime.errorOccurred.connect(self.errorOccurred)
        runtime.runFinished.connect(self.runFinished)

    @Slot(str, result=str)
    def getCatalog(self, suite: str) -> str:
        try:
            return self._controller.catalog_json(suite or "frontier_v3")
        except (ValueError, OSError) as exc:
            self.errorOccurred.emit(str(exc))
            return "{}"

    @Slot(result=str)
    def getDoctor(self) -> str:
        try:
            return self._controller.doctor_json()
        except (ValueError, OSError) as exc:
            self.errorOccurred.emit(str(exc))
            return "{}"

    @Slot(str, result=bool)
    def saveDoctorProfile(self, payload: str) -> bool:
        try:
            self._controller.save_doctor_profile(payload)
            self.doctorChanged.emit(self._controller.doctor_json())
        except (TypeError, ValueError, OSError) as exc:
            self.errorOccurred.emit(str(exc))
            return False
        return True

    @Slot(str, result=bool)
    def installHarness(self, name: str) -> bool:
        try:
            self._runtime.install_harness(name)
        except (ValueError, RuntimeError, OSError) as exc:
            self.errorOccurred.emit(str(exc))
            return False
        return True

    @Slot(str, result=bool)
    def startRun(self, payload: str) -> bool:
        try:
            self._runtime.start_run(payload)
        except (TypeError, ValueError, RuntimeError) as exc:
            self.errorOccurred.emit(str(exc))
            return False
        return True
