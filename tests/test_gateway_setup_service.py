from __future__ import annotations

from config.settings import SettingsStore
from core import doctor_service
from core.doctor_service import DoctorProfile, DoctorService
from core.inference_setup import GatewayProbeResult


def _report():
    return {
        "system": {},
        "ready": True,
        "harnesses": [
            {"name": "piagent", "installed": True, "ready": True},
            {"name": "claude", "installed": True, "ready": True},
            {"name": "agentzero", "installed": False, "ready": False},
        ],
    }


def test_test_and_configure_saves_only_after_openai_probe_success(tmp_path, monkeypatch):
    service = DoctorService(SettingsStore(tmp_path / "settings.json"))
    monkeypatch.setattr(service, "inspect", lambda cancellation_check=None: _report())
    monkeypatch.setattr(
        doctor_service,
        "probe_openai_gateway",
        lambda *args, **kwargs: GatewayProbeResult(
            "openai",
            "http://127.0.0.1:8080/v1",
            "Ornith",
            True,
            True,
            True,
            ("Ornith",),
            "Ornith",
        ),
    )
    saved = []
    original_save = service.save_profile

    def record_save(profile):
        saved.append(profile)
        return original_save(profile)

    monkeypatch.setattr(service, "save_profile", record_save)
    report = service.test_and_configure(
        DoctorProfile("Ornith", "http://127.0.0.1:8080/v1/", "")
    )

    assert report["gateway"]["saved"] is True
    assert saved == [DoctorProfile("Ornith", "http://127.0.0.1:8080/v1", "")]
    by_name = {item["name"]: item for item in report["harnesses"]}
    assert by_name["piagent"]["binding"]["status"] == "configured"
    assert by_name["claude"]["binding"]["status"] == "needs_anthropic_endpoint"
    assert by_name["agentzero"]["binding"]["status"] == "external_service"


def test_test_and_configure_does_not_replace_saved_profile_on_failed_model_probe(
    tmp_path, monkeypatch
):
    store = SettingsStore(tmp_path / "settings.json")
    service = DoctorService(store)
    service.save_profile(DoctorProfile("Old", "http://127.0.0.1:9000/v1", ""))
    monkeypatch.setattr(service, "inspect", lambda cancellation_check=None: _report())
    monkeypatch.setattr(
        doctor_service,
        "probe_openai_gateway",
        lambda *args, **kwargs: GatewayProbeResult(
            "openai",
            "http://127.0.0.1:8080/v1",
            "Missing",
            True,
            False,
            False,
            ("Ornith",),
            error="Selected model is not present in /models",
        ),
    )

    report = service.test_and_configure(
        DoctorProfile("Missing", "http://127.0.0.1:8080/v1", "")
    )

    assert report["gateway"]["saved"] is False
    assert service.load_profile().model == "Old"


def test_failed_anthropic_probe_does_not_block_openai_profile_save(tmp_path, monkeypatch):
    service = DoctorService(SettingsStore(tmp_path / "settings.json"))
    monkeypatch.setattr(service, "inspect", lambda cancellation_check=None: _report())
    monkeypatch.setattr(
        doctor_service,
        "probe_openai_gateway",
        lambda *args, **kwargs: GatewayProbeResult(
            "openai", "http://127.0.0.1:8080/v1", "Ornith", True, True, True,
            ("Ornith",), "Ornith"
        ),
    )
    monkeypatch.setattr(
        doctor_service,
        "probe_anthropic_gateway",
        lambda *args, **kwargs: GatewayProbeResult(
            "anthropic", "http://127.0.0.1:8082", "Ornith", True, True, False,
            error="HTTP 404"
        ),
    )

    report = service.test_and_configure(
        DoctorProfile("Ornith", "http://127.0.0.1:8080/v1", "http://127.0.0.1:8082")
    )
    assert report["gateway"]["saved"] is True
    claude = next(item for item in report["harnesses"] if item["name"] == "claude")
    assert claude["binding"]["status"] == "anthropic_probe_failed"
