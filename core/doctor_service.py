from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from config.settings import AppSettings, SettingsStore
from core.benchmark import doctor
from core.benchmark.local_gateway import binding_summary
from core.inference_setup import (
    discover_openai_models,
    normalize_endpoint,
    probe_anthropic_gateway,
    probe_openai_gateway,
)


@dataclass(frozen=True)
class DoctorProfile:
    model: str
    openai_url: str
    anthropic_url: str


class DoctorService:
    """Application-facing setup API and owner of the canonical inference profile."""

    def __init__(self, settings: SettingsStore | None = None) -> None:
        self._settings = settings or SettingsStore()
        self._protected_environment = frozenset(
            key for key in doctor.PROFILE_ENV_KEYS if key in os.environ
        )

    def inspect(
        self,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> dict:
        report = doctor.inspect(cancellation_check=cancellation_check)
        profile = self.load_profile()
        for item in report["harnesses"]:
            recipe = doctor.SPECS[item["name"]].install()
            item["install"] = {
                "command": list(recipe.command) if recipe.command else None,
                "manual_command": recipe.shell,
                "docs": recipe.docs,
                "note": recipe.note,
                "automatic": recipe.command is not None,
            }
            ready = bool(item.get("ready", item["installed"]))
            item["status"] = "ready" if ready else "blocked" if item["installed"] else "missing"
            if profile.openai_url and profile.model:
                item["binding"] = binding_summary(
                    item["name"],
                    endpoint=profile.openai_url,
                    model=profile.model,
                    anthropic_url=profile.anthropic_url,
                )
        report["profile"] = {
            "model": profile.model,
            "openai_url": profile.openai_url,
            "anthropic_url": profile.anthropic_url,
        }
        return report

    def load_profile(self) -> DoctorProfile:
        value = self._settings.load()
        return DoctorProfile(value.model, value.openai_url, value.anthropic_url)

    def save_profile(self, profile: DoctorProfile) -> Path:
        normalized = DoctorProfile(
            str(profile.model or "").strip(),
            normalize_endpoint(profile.openai_url) if profile.openai_url else "",
            normalize_endpoint(profile.anthropic_url, anthropic=True)
            if profile.anthropic_url
            else "",
        )
        path = self._settings.save(self._settings_value(normalized))
        self.apply_runtime_environment(normalized)
        return path

    def discover_models(
        self,
        openai_url: str,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> dict:
        endpoint, models = discover_openai_models(
            openai_url,
            cancellation_check=cancellation_check,
        )
        return {"endpoint": endpoint, "models": list(models)}

    def test_and_configure(
        self,
        profile: DoctorProfile,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> dict:
        """Verify the canonical model route, then persist one shared profile.

        The OpenAI-compatible model route is the mandatory benchmark gateway.
        Anthropic is optional and tested independently so a missing Claude
        gateway never blocks Pi/OpenCode/Goose/Letta/Hermes/DeepSeek setup.
        """
        normalized = DoctorProfile(
            str(profile.model or "").strip(),
            normalize_endpoint(profile.openai_url),
            normalize_endpoint(profile.anthropic_url, anthropic=True)
            if profile.anthropic_url
            else "",
        )
        openai = probe_openai_gateway(
            normalized.openai_url,
            normalized.model,
            cancellation_check=cancellation_check,
        )
        anthropic = None
        if normalized.anthropic_url:
            anthropic = probe_anthropic_gateway(
                normalized.anthropic_url,
                normalized.model,
                cancellation_check=cancellation_check,
            )

        saved = False
        if openai.ready:
            self.save_profile(normalized)
            saved = True

        report = self.inspect(cancellation_check)
        report["gateway"] = {
            "openai": openai.to_dict(),
            "anthropic": anthropic.to_dict() if anthropic is not None else None,
            "saved": saved,
        }
        for item in report["harnesses"]:
            binding = binding_summary(
                item["name"],
                endpoint=normalized.openai_url,
                model=normalized.model,
                anthropic_url=normalized.anthropic_url,
            )
            if item["name"] == "claude" and anthropic is not None and not anthropic.ready:
                binding["status"] = "anthropic_probe_failed"
                binding["automatic"] = False
            if not item["installed"]:
                binding["runtime_status"] = "missing"
            elif not item.get("ready", item["installed"]):
                binding["runtime_status"] = "blocked"
            else:
                binding["runtime_status"] = "ready"
            item["binding"] = binding
        return report

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
