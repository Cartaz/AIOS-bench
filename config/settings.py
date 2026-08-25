from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    model: str = ""
    openai_url: str = ""
    anthropic_url: str = ""


class SettingsStore:
    """Single owner for persistent application settings."""

    def __init__(self, path: Path | None = None) -> None:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        self.path = path or (base / "aios-bench" / "settings.json")

    def load(self) -> AppSettings:
        if not self.path.is_file():
            return AppSettings()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppSettings()
        if not isinstance(value, dict):
            return AppSettings()
        return AppSettings(
            model=self._string(value.get("model")),
            openai_url=self._string(value.get("openai_url")),
            anthropic_url=self._string(value.get("anthropic_url")),
        )

    def save(self, settings: AppSettings) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "aios-bench/settings/v1",
            "model": settings.model.strip(),
            "openai_url": settings.openai_url.strip().rstrip("/"),
            "anthropic_url": settings.anthropic_url.strip().rstrip("/"),
        }
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)
        return self.path

    @staticmethod
    def _string(value: object) -> str:
        return value.strip() if isinstance(value, str) else ""
