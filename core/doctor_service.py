from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from aios_bench import doctor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DoctorProfile:
    model: str
    openai_url: str
    anthropic_url: str


class DoctorService:
    """Application-facing Doctor API; keeps UI away from environment/filesystem details."""

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
        value = doctor.load_profile()
        return DoctorProfile(
            model=str(value.get("model") or ""),
            openai_url=str(value.get("openai_compatible_url") or ""),
            anthropic_url=str(value.get("anthropic_compatible_url") or ""),
        )

    def save_profile(self, profile: DoctorProfile) -> Path:
        return doctor.write_profile(
            model=profile.model,
            openai_url=profile.openai_url,
            anthropic_url=profile.anthropic_url,
        )

    def install_harness(self, name: str) -> dict:
        if name not in doctor.SPECS:
            raise ValueError(f"Unknown harness: {name}")
        recipe = doctor.SPECS[name].install()
        if recipe.command is None:
            raise ValueError(
                "This harness requires guided manual installation; use the displayed official instructions."
            )
        if not doctor._run_install(recipe):
            raise RuntimeError(f"Installation command failed for {name}")
        return self.inspect()
