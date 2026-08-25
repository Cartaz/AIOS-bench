from __future__ import annotations

from config.settings import SettingsStore
from core.doctor_service import DoctorProfile, DoctorService
from aios_bench import doctor


def test_doctor_service_marks_remote_shell_installers_manual(monkeypatch):
    monkeypatch.setattr(doctor, "_probe", lambda executable: (False, None, None))
    monkeypatch.setattr(doctor, "_agentzero_ready", lambda: False)
    report = DoctorService().inspect()
    by_name = {item["name"]: item for item in report["harnesses"]}
    assert by_name["goose"]["install"]["automatic"] is False
    assert by_name["goose"]["install"]["manual_command"].startswith("curl -fsSL")
    assert by_name["hermes"]["install"]["automatic"] is False
    assert by_name["piagent"]["install"]["automatic"] is True


def test_doctor_service_rejects_automatic_remote_shell_install(monkeypatch):
    service = DoctorService()
    called = False

    def fail_if_called(name):
        nonlocal called
        called = True
        return True

    monkeypatch.setattr(doctor, "install_harness", fail_if_called)
    try:
        service.install_harness("goose")
    except ValueError as exc:
        assert "guided manual installation" in str(exc)
    else:
        raise AssertionError("Goose shell installer must stay manual")
    assert called is False


def test_doctor_service_uses_public_install_contract(monkeypatch):
    service = DoctorService()
    called = []
    monkeypatch.setattr(doctor, "install_harness", lambda name: called.append(name) or True)
    monkeypatch.setattr(service, "inspect", lambda: {"ready": True})

    assert service.install_harness("piagent") == {"ready": True}
    assert called == ["piagent"]


def test_doctor_service_profile_round_trip(tmp_path):
    service = DoctorService(SettingsStore(tmp_path / "settings.json"))
    service.save_profile(DoctorProfile("Ornith", "http://localhost:8080/v1", "http://localhost:8080"))
    loaded = service.load_profile()
    assert loaded.model == "Ornith"
    assert loaded.openai_url == "http://localhost:8080/v1"
    assert loaded.anthropic_url == "http://localhost:8080"
