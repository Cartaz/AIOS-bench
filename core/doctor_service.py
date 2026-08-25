from __future__ import annotations

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

    def inspect(self) -> dict:
        report = doctor.inspect()
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
        return self._settings.save(
            AppSettings(
                model=profile.model,
                openai_url=profile.openai_url,
                anthropic_url=profile.anthropic_url,
            )
        )

    def validate_install(self, name: str) -> None:
        if name not in doctor.SPECS:
            raise ValueError(f"Unknown harness: {name}")
        recipe = doctor.SPECS[name].install()
        if recipe.command is None:
            raise ValueError(
                "This harness requires guided manual installation; use the displayed official instructions."
            )

    def install_harness(self, name: str) -> dict:
        self.validate_install(name)
        if not doctor.install_harness(name):
            raise RuntimeError(f"Installation command failed for {name}")
        return self.inspect()
