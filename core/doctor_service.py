from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from config.settings import AppSettings, SettingsStore
from core.benchmark import doctor


@dataclass(frozen=True)
class DoctorProfile:
    model: str
    openai_url: str
    anthropic_url: str


class DoctorService:
    """Application-facing Doctor API; keeps UI away from environment/filesystem details."""

    def __init__(self, settings: SettingsStore | None = None) -> None:
        self._settings = settings or SettingsStore()
        # Environment values supplied before the service starts are explicit
        # operator overrides. Saved desktop settings own only the remaining keys.
        self._protected_environment = frozenset(
            key for key in doctor.PROFILE_ENV_KEYS if key in os.environ
        )

    def inspect(
        self,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> dict:
        report = doctor.inspect(cancellation_check=cancellation_check)
        for item in report["harnesses"]:
            recipe = doctor.SPECS[item["name"]].install()
            item["install"] = {
                "command": list(recipe.command) if recipe.command else None,
                "manual_command": recipe.shell,
                "docs": recipe.docs,
                "note": recipe.note,
                "automatic": recipe.command is not None,
            }
            item["status"] = "ready" if item["installed"] else "missing"
        return report

    def load_profile(self) -> DoctorProfile:
        value = self._settings.load()
        return DoctorProfile(value.model, value.openai_url, value.anthropic_url)

    def save_profile(self, profile: DoctorProfile) -> Path:
        path = self._settings.save(self._settings_value(profile))
        self.apply_runtime_environment(profile)
        return path

    def apply_runtime_environment(self, profile: DoctorProfile | None = None) -> dict[str, str]:
        """Apply the profile without overriding process-level operator settings."""
        current = profile or self.load_profile()
        return doctor.apply_settings_environment(
            self._settings_value(current),
            protected_keys=self._protected_environment,
        )

    @staticmethod
    def _settings_value(profile: DoctorProfile) -> AppSettings:
        return AppSettings(
            model=profile.model,
            openai_url=profile.openai_url,
            anthropic_url=profile.anthropic_url,
        )

    def validate_install(self, name: str) -> None:
        if name not in doctor.SPECS:
            raise ValueError(f"Unknown harness: {name}")
        recipe = doctor.SPECS[name].install()
        if recipe.command is None:
            raise ValueError(
                "This harness requires guided manual installation; use the displayed official instructions."
            )

    def install_harness(
        self,
        name: str,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> dict:
        self.validate_install(name)
        if not doctor.install_harness(name, cancellation_check=cancellation_check):
            if cancellation_check is not None and cancellation_check():
                raise RuntimeError(f"Installation cancelled for {name}")
            raise RuntimeError(f"Installation command failed for {name}")
        return self.inspect(cancellation_check)
