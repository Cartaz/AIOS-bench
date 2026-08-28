from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path

from config.settings import SettingsStore

from .cancellation import CancellationToken
from .doctor_service import DoctorProfile, DoctorService
from .run_service import BenchmarkService, PreparedRun, RunRequest

EventCallback = Callable[[dict[str, object]], None]


class AppController:
    """Coordinates application services without owning Qt or presentation lifecycle."""

    def __init__(self, repo_root: Path, settings: SettingsStore | None = None) -> None:
        self._benchmark = BenchmarkService(repo_root)
        self._doctor = DoctorService(settings or SettingsStore())

    def catalog_json(self, suite: str = "frontier_v3") -> str:
        return json.dumps(self._benchmark.catalog(suite), ensure_ascii=False)

    def doctor_json(
        self,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> str:
        return self._doctor_payload_json(self._doctor.inspect(cancellation_check))

    def _doctor_payload_json(self, report: dict) -> str:
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
        return str(self._doctor.save_profile(profile))

    def validate_install_harness(self, name: str) -> None:
        self._doctor.validate_install(name)

    def install_harness(
        self,
        name: str,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> str:
        report = self._doctor.install_harness(name, cancellation_check)
        return self._doctor_payload_json(report)

    def prepare_run(self, payload: str) -> PreparedRun:
        raw = self._json_object(payload, "Run configuration")
        allowed = {field.name for field in fields(RunRequest)}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"Unknown run settings: {', '.join(unknown)}")
        raw["harnesses"] = self._string_tuple(raw.get("harnesses"), "Harnesses")
        raw["task_ids"] = self._string_tuple(raw.get("task_ids"), "Task ids")
        request = RunRequest(**raw)
        return self._benchmark.prepare(request)

    def run_benchmark(
        self,
        prepared: PreparedRun,
        on_event: EventCallback,
        cancellation_token: CancellationToken | None = None,
    ) -> dict[str, object]:
        self._doctor.apply_runtime_environment()
        return self._benchmark.run(prepared, on_event, cancellation_token)

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

    @staticmethod
    def _string_tuple(value: object, label: str) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, list):
            raise ValueError(f"{label} must be an array")
        if not all(isinstance(item, str) and item for item in value):
            raise ValueError(f"{label} must contain non-empty strings")
        return tuple(value)
