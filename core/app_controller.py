from __future__ import annotations

import json
import logging
from dataclasses import fields
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from .doctor_service import DoctorProfile, DoctorService
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
    doctor_changed = Signal(str)
    run_state_changed = Signal(str)
    progress_changed = Signal(str)
    error_occurred = Signal(str)
    run_finished = Signal(str)

    def __init__(self, repo_root: Path) -> None:
        super().__init__()
        self._service = BenchmarkService(repo_root)
        self._doctor = DoctorService()
        self._thread: QThread | None = None
        self._worker: RunWorker | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def catalog_json(self, suite: str = "frontier_v3") -> str:
        return json.dumps(self._service.catalog(suite), ensure_ascii=False)

    def doctor_json(self) -> str:
        report = self._doctor.inspect()
        profile = self._doctor.load_profile()
        payload = {
            "report": report,
            "profile": {
                "model": profile.model,
                "openai_url": profile.openai_url,
                "anthropic_url": profile.anthropic_url,
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    def save_doctor_profile(self, payload: str) -> str:
        raw = self._json_object(payload, "Doctor profile")
        allowed = {"model", "openai_url", "anthropic_url"}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"Unknown profile settings: {', '.join(unknown)}")
        profile = DoctorProfile(
            model=self._string(raw.get("model")),
            openai_url=self._string(raw.get("openai_url")),
            anthropic_url=self._string(raw.get("anthropic_url")),
        )
        path = self._doctor.save_profile(profile)
        value = self.doctor_json()
        self.doctor_changed.emit(value)
        return str(path)

    def install_harness(self, name: str) -> str:
        report = self._doctor.install_harness(name.strip())
        value = json.dumps({"report": report}, ensure_ascii=False)
        self.doctor_changed.emit(self.doctor_json())
        return value

    def start_run(self, payload: str) -> None:
        if self._running:
            raise RuntimeError("A benchmark run is already active")
        raw = self._json_object(payload, "Run configuration")
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

    @staticmethod
    def _json_object(payload: str, label: str) -> dict:
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} must be valid JSON") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"{label} must be an object")
        return raw

    @staticmethod
    def _string(value: object) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("Profile values must be strings")
        return value.strip()

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
