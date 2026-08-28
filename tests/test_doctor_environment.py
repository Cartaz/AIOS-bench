from __future__ import annotations

import os
from pathlib import Path

import pytest

from config.settings import SettingsStore
from core.doctor_service import DoctorProfile, DoctorService


def test_saved_profile_updates_and_clears_only_profile_owned_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("AIOS_BENCH_ENDPOINT", raising=False)
    monkeypatch.delenv("AIOS_BENCH_CLAUDE_BASE_URL", raising=False)
    service = DoctorService(SettingsStore(tmp_path / "settings.json"))

    service.save_profile(
        DoctorProfile(
            "model-a",
            "http://127.0.0.1:8080/v1",
            "http://127.0.0.1:8080",
        )
    )
    assert os.environ["AIOS_BENCH_ENDPOINT"] == "http://127.0.0.1:8080/v1"
    assert os.environ["AIOS_BENCH_CLAUDE_BASE_URL"] == "http://127.0.0.1:8080"

    service.save_profile(DoctorProfile("model-b", "http://127.0.0.1:9090/v1", ""))
    assert os.environ["AIOS_BENCH_ENDPOINT"] == "http://127.0.0.1:9090/v1"
    assert "AIOS_BENCH_CLAUDE_BASE_URL" not in os.environ


def test_process_level_gateway_values_remain_authoritative(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://operator.example/v1")
    monkeypatch.setenv("AIOS_BENCH_CLAUDE_BASE_URL", "http://operator.example")
    service = DoctorService(SettingsStore(tmp_path / "settings.json"))

    service.save_profile(
        DoctorProfile(
            "model",
            "http://profile.example/v1",
            "http://profile.example",
        )
    )

    assert os.environ["AIOS_BENCH_ENDPOINT"] == "http://operator.example/v1"
    assert os.environ["AIOS_BENCH_CLAUDE_BASE_URL"] == "http://operator.example"
