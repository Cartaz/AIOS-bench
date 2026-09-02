from __future__ import annotations

import json
from pathlib import Path

from core.benchmark import doctor


def test_inspect_reports_all_active_harnesses(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "_probe",
        lambda executable: (
            bool(executable),
            f"/bin/{executable}" if executable else None,
            "1.2.3" if executable else None,
        ),
    )
    monkeypatch.setattr(
        doctor,
        "_node_runtime",
        lambda: {"path": "/bin/node", "version": "v24.0.0", "compatible": True},
    )
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(doctor, "_agentzero_ready", lambda: True)
    report = doctor.inspect()
    names = [item["name"] for item in report["harnesses"]]
    assert names == [
        "hermes",
        "piagent",
        "opencode",
        "goose",
        "letta",
        "agentzero",
        "claude",
        "deepseek",
    ]
    assert report["ready"] is True
    assert all(item["ready"] for item in report["harnesses"])
    assert all(item["docs"].startswith("https://") for item in report["harnesses"])


def test_deepseek_recipe_is_pinned_and_uses_official_cli_package():
    recipe = doctor._deepseek_recipe()
    assert recipe.command == (
        "npm",
        "install",
        "-g",
        f"@deepseek-ai/dsh@{doctor.DEEPSEEK_HARNESS_VERSION}",
    )
    assert "deepseek-ai/deepseek-harness" in recipe.docs
    assert doctor.DEEPSEEK_NODE_RANGE in recipe.note
    assert "Node 23 is not supported" in recipe.note


def test_deepseek_node_engine_range_is_exact():
    assert doctor._node_version_supported("v22.19.0") is True
    assert doctor._node_version_supported("22.21.3") is True
    assert doctor._node_version_supported("v22.18.9") is False
    assert doctor._node_version_supported("v23.11.0") is False
    assert doctor._node_version_supported("v24.0.0") is True
    assert doctor._node_version_supported("v25.4.1") is True
    assert doctor._node_version_supported("garbage") is False
    assert doctor._node_version_supported(None) is False


def test_inspect_marks_installed_deepseek_blocked_on_wrong_node(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "_probe",
        lambda executable: (
            bool(executable),
            f"/bin/{executable}" if executable else None,
            "1.2.3" if executable else None,
        ),
    )
    monkeypatch.setattr(
        doctor,
        "_node_runtime",
        lambda: {"path": "/bin/node", "version": "v23.11.0", "compatible": False},
    )
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(doctor, "_agentzero_ready", lambda: True)

    report = doctor.inspect()
    deepseek = next(item for item in report["harnesses"] if item["name"] == "deepseek")

    assert deepseek["installed"] is True
    assert deepseek["ready"] is False
    assert any(doctor.DEEPSEEK_NODE_RANGE in issue for issue in deepseek["issues"])
    assert report["ready"] is False
    rendered = doctor.render_report(report)
    assert "BLOCKED" in rendered
    assert "DeepSeek Harness" in rendered


def test_inspect_marks_installed_deepseek_blocked_without_bubblewrap(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "_probe",
        lambda executable: (
            bool(executable),
            f"/bin/{executable}" if executable else None,
            "1.2.3" if executable else None,
        ),
    )
    monkeypatch.setattr(
        doctor,
        "_node_runtime",
        lambda: {"path": "/bin/node", "version": "v24.0.0", "compatible": True},
    )
    monkeypatch.setattr(
        doctor.shutil,
        "which",
        lambda name: None if name == "bwrap" else f"/bin/{name}",
    )
    monkeypatch.setattr(doctor, "_agentzero_ready", lambda: True)

    report = doctor.inspect()
    deepseek = next(item for item in report["harnesses"] if item["name"] == "deepseek")

    assert deepseek["installed"] is True
    assert deepseek["ready"] is False
    assert deepseek["issues"] == ["requires Bubblewrap for isolated DSH_HOME"]


def test_profile_round_trip_and_environment_does_not_override_explicit_values(monkeypatch, tmp_path: Path):
    path = tmp_path / "settings.json"
    doctor.write_profile(
        model="Ornith",
        openai_url="http://127.0.0.1:8080/v1/",
        anthropic_url="http://127.0.0.1:8082/",
        path=path,
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value["schema"] == doctor.PROFILE_SCHEMA
    assert value["model"] == "Ornith"
    assert value["openai_url"] == "http://127.0.0.1:8080/v1"
    assert value["anthropic_url"] == "http://127.0.0.1:8082"

    monkeypatch.setenv("AIOS_BENCH_ENDPOINT", "http://explicit.test/v1")
    loaded = doctor.apply_profile_environment(path)
    assert loaded["model"] == "Ornith"
    assert doctor.os.environ["AIOS_BENCH_ENDPOINT"] == "http://explicit.test/v1"
    assert doctor.os.environ["AIOS_BENCH_CLAUDE_BASE_URL"] == "http://127.0.0.1:8082"


def test_opencode_recipe_keeps_privileged_pacman_install_manual_on_cachyos(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    monkeypatch.setattr(doctor, "_linux_id", lambda: "cachyos")
    recipe = doctor._opencode_recipe()
    assert recipe.command is None
    assert recipe.shell == "sudo pacman -S --needed opencode"
    assert "manual" in recipe.note.lower()


def test_remote_shell_installers_are_never_executed(monkeypatch):
    calls = []
    monkeypatch.setattr(doctor.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    answers = iter(["y", "n"])
    monkeypatch.setattr(
        doctor,
        "inspect",
        lambda: {
            "schema": "aios-bench/doctor-report/v1",
            "system": {
                "platform": "Linux",
                "release": "x",
                "machine": "x86_64",
                "distribution": "cachyos",
                "python": "3.14",
                "node": "/bin/node",
                "npm": "/bin/npm",
                "bubblewrap": "/bin/bwrap",
            },
            "harnesses": [
                {
                    "name": "goose",
                    "display_name": "Goose",
                    "installed": False,
                    "path": None,
                    "version": None,
                    "docs": "https://block.github.io/goose/",
                    "config_hint": doctor.SPECS["goose"].config_hint,
                }
            ],
            "ready": False,
        },
    )
    monkeypatch.setattr(doctor, "load_profile", lambda path=doctor.DEFAULT_PROFILE: {})
    code = doctor.run_wizard(
        setup=True,
        repair=False,
        check_only=False,
        input_fn=lambda _: next(answers),
    )
    assert code == 1
    assert calls == []


def test_check_mode_is_non_mutating(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "inspect",
        lambda: {
            "schema": "aios-bench/doctor-report/v1",
            "system": {
                "platform": "Linux",
                "release": "x",
                "machine": "x86_64",
                "distribution": "arch",
                "python": "3.14",
                "node": None,
                "npm": None,
                "bubblewrap": None,
            },
            "harnesses": [],
            "ready": False,
        },
    )
    monkeypatch.setattr(
        doctor,
        "install_harness",
        lambda name: (_ for _ in ()).throw(AssertionError("must not install")),
    )
    assert doctor.run_wizard(
        setup=False,
        repair=False,
        check_only=True,
        input_fn=lambda _: "y",
    ) == 1