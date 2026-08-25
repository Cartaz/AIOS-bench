from __future__ import annotations

import json
import logging
from dataclasses import fields
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from .run_service import BenchmarkService, RunRequest

logger = logging.getLogger(__name__)


class RunWorker(QObject):
    event = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, service: BenchmarkService, request: RunRequest) -> None:
        super().__init__()
        self._service = service
        self._request = request

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.run(self._request, self.event.emit)
        except Exception:
            logger.exception("Benchmark run failed")
            self.failed.emit("Benchmark run failed. See application log for details.")
        else:
            self.finished.emit(result)


class AppController(QObject):
    catalog_changed = Signal(str)
    run_state_changed = Signal(str)
    progress_changed = Signal(str)
    error_occurred = Signal(str)
    run_finished = Signal(str)

    def __init__(self, repo_root: Path) -> None:
        super().__init__()
        self._service = BenchmarkService(repo_root)
        self._thread: QThread | None = None
        self._worker: RunWorker | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def catalog_json(self, suite: str = "frontier_v3") -> str:
        return json.dumps(self._service.catalog(suite), ensure_ascii=False)

    def start_run(self, payload: str) -> None:
        if self._running:
            raise RuntimeError("A benchmark run is already active")
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Run configuration must be valid JSON") from exc
        if not isinstance(raw, dict):
            raise ValueError("Run configuration must be an object")
        allowed = {field.name for field in fields(RunRequest)}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"Unknown run settings: {', '.join(unknown)}")
        raw["harnesses"] = tuple(raw.get("harnesses") or ())
        raw["task_ids"] = tuple(raw.get("task_ids") or ())
        request = RunRequest(**raw)
        self._service.validate_request(request)

        thread = QThread(self)
        worker = RunWorker(self._service, request)
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
        self._running = True
        self.run_state_changed.emit(json.dumps({"running": True}))
        thread.start()

    @Slot(object)
    def _on_event(self, event: object) -> None:
        self.progress_changed.emit(json.dumps(event, ensure_ascii=False))

    @Slot(object)
    def _on_finished(self, result: object) -> None:
        self.run_finished.emit(json.dumps(result, ensure_ascii=False))

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.error_occurred.emit(message)

    @Slot()
    def _thread_finished(self) -> None:
        self._running = False
        self._worker = None
        self._thread = None
        self.run_state_changed.emit(json.dumps({"running": False}))

    def shutdown(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            logger.warning("Shutdown requested while a benchmark run is active")
