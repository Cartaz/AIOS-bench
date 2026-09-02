from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from core.app_controller import AppController

from .runtime import DesktopRuntime


class Bridge(QObject):
    catalogChanged = Signal(str)
    doctorChanged = Signal(str)
    modelsDiscovered = Signal(str)
    runStateChanged = Signal(str)
    progressChanged = Signal(str)
    errorOccurred = Signal(str)
    runFinished = Signal(str)

    def __init__(self, controller: AppController, runtime: DesktopRuntime) -> None:
        super().__init__()
        self._controller = controller
        self._runtime = runtime
        runtime.doctorChanged.connect(self.doctorChanged)
        runtime.modelsDiscovered.connect(self.modelsDiscovered)
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

    @Slot(result=bool)
    def getDoctor(self) -> bool:
        try:
            self._runtime.inspect_doctor()
        except (ValueError, RuntimeError, OSError) as exc:
            self.errorOccurred.emit(str(exc))
            return False
        return True

    @Slot(str, result=bool)
    def discoverModels(self, openai_url: str) -> bool:
        try:
            self._runtime.discover_models(openai_url)
        except (TypeError, ValueError, RuntimeError, OSError) as exc:
            self.errorOccurred.emit(str(exc))
            return False
        return True

    @Slot(str, result=bool)
    def testAndConfigure(self, payload: str) -> bool:
        try:
            self._runtime.test_and_configure(payload)
        except (TypeError, ValueError, RuntimeError, OSError) as exc:
            self.errorOccurred.emit(str(exc))
            return False
        return True

    @Slot(str, result=bool)
    def saveDoctorProfile(self, payload: str) -> bool:
        if self._runtime.is_busy:
            self.errorOccurred.emit("Another background operation is already active")
            return False
        try:
            self._controller.save_doctor_profile(payload)
            self._runtime.inspect_doctor()
        except (TypeError, ValueError, RuntimeError, OSError) as exc:
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

    @Slot(result=bool)
    def cancelRun(self) -> bool:
        return self._runtime.cancel_run()