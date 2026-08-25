from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Callable

from .doctor_service import DoctorProfile, DoctorService
from .run_service import BenchmarkService, RunRequest

EventCallback = Callable[[dict[str, object]], None]


class AppController:
    """Coordinates application services without owning Qt or presentation lifecycle."""

    def __init__(self, repo_root: Path) -> None:
        self._benchmark = BenchmarkService(repo_root)
        self._doctor = DoctorService()

    def catalog_json(self, suite: str = "frontier_v3") -> str:
        return json.dumps(self._benchmark.catalog(suite), ensure_ascii=False)

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
        return str(self._doctor.save_profile(profile))

    def validate_install_harness(self, name: str) -> None:
        self._doctor.validate_install(name)

    def install_harness(self, name: str) -> dict:
        return self._doctor.install_harness(name)

    def prepare_run(self, payload: str) -> RunRequest:
        raw = self._json_object(payload, "Run configuration")
        allowed = {field.name for field in fields(RunRequest)}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"Unknown run settings: {', '.join(unknown)}")
        raw["harnesses"] = tuple(raw.get("harnesses") or ())
        raw["task_ids"] = tuple(raw.get("task_ids") or ())
        request = RunRequest(**raw)
        self._benchmark.validate_request(request)
        return request

    def run_benchmark(self, request: RunRequest, on_event: EventCallback) -> dict[str, object]:
        return self._benchmark.run(request, on_event)

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
