import json
from pathlib import Path

from aios_bench.adapters import Adapter, AgentInvocation
from aios_bench.harness_process import prepare_harness_process
from aios_bench.sandbox import SandboxPlan


class _Adapter(Adapter):
    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        return AgentInvocation(
            ["fake-harness", prompt],
            {
                "AIOS_BENCH_WORKSPACE": str(workspace),
                "HOME": "/home/real-user",
                "ADAPTER_OWNED_VALUE": "kept",
            },
        )


class _SettingsAdapter(_Adapter):
    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        invocation = super().build(prompt, workspace, model)
        return AgentInvocation(
            ["claude", "--settings", '{"allowedTools":["Read"]}', prompt],
            invocation.environment,
        )


def _patch_boundary(monkeypatch):
    def fake_with_project_bin(environment=None):
        if environment is None:
            result = {
                "PATH": "/usr/bin",
                "HOME": "/home/real-user",
                "OPENCODE_CONFIG_DIR": "/home/real-user/.opencode",
                "GOOSE_PATH_ROOT": "/home/real-user/.config/goose",
            }
        else:
            result = dict(environment)
            result.setdefault("PATH", "/usr/bin")
        result["PATH"] = f"/project/.venv/bin:{result['PATH']}"
        return result

    monkeypatch.setattr("aios_bench.harness_process.with_project_bin", fake_with_project_bin)
    monkeypatch.setattr(
        "aios_bench.harness_process.workspace_sandbox",
        lambda adapter_name, workspace: SandboxPlan("test"),
    )


def _claude_settings(command: list[str]) -> dict:
    index = command.index("--settings")
    return json.loads(command[index + 1])


def test_claude_process_uses_isolated_runtime_environment(monkeypatch, tmp_path):
    _patch_boundary(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "benchmark-key")
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", "/home/real-user/.opencode")
    monkeypatch.setenv("GOOSE_PATH_ROOT", "/home/real-user/.config/goose")

    prepared = prepare_harness_process(
        adapter_name="claude",
        adapter=_Adapter(),
        prompt="probe",
        workspace=tmp_path,
        model="Ornith",
    )

    environment = prepared.environment
    assert environment["HOME"] == "/tmp/aios-bench-claude/home"
    assert environment["TMPDIR"] == "/tmp/aios-bench-claude/tmp"
    assert environment["XDG_CONFIG_HOME"] == "/tmp/aios-bench-claude/xdg-config"
    assert environment["XDG_DATA_HOME"] == "/tmp/aios-bench-claude/xdg-data"
    assert environment["XDG_STATE_HOME"] == "/tmp/aios-bench-claude/xdg-state"
    assert environment["XDG_CACHE_HOME"] == "/tmp/aios-bench-claude/xdg-cache"
    assert environment["CLAUDE_BASH_NO_LOGIN"] == "1"
    assert environment["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8080"
    assert environment["ANTHROPIC_API_KEY"] == "benchmark-key"
    assert environment["ADAPTER_OWNED_VALUE"] == "kept"
    assert environment["AIOS_BENCH_WORKSPACE"] == str(tmp_path)
    assert "OPENCODE_CONFIG_DIR" not in environment
    assert "GOOSE_PATH_ROOT" not in environment

    assert prepared.command[-1] == "probe"
    settings = _claude_settings(prepared.command)
    assert settings["allowedTools"] == [
        "Bash",
        "Edit",
        "NotebookEdit",
        "Read",
        "Task",
        "WebFetch",
        "WebSearch",
        "Write",
    ]


def test_claude_process_policy_cannot_be_overridden_by_extra_environment(monkeypatch, tmp_path):
    _patch_boundary(monkeypatch)

    prepared = prepare_harness_process(
        adapter_name="claude",
        adapter=_Adapter(),
        prompt="probe",
        workspace=tmp_path,
        model="Ornith",
        extra_environment={"HOME": "/home/escape", "XDG_CONFIG_HOME": "/home/config"},
    )

    assert prepared.environment["HOME"] == "/tmp/aios-bench-claude/home"
    assert prepared.environment["XDG_CONFIG_HOME"] == "/tmp/aios-bench-claude/xdg-config"


def test_claude_process_replaces_conflicting_inline_settings(monkeypatch, tmp_path):
    _patch_boundary(monkeypatch)

    prepared = prepare_harness_process(
        adapter_name="claude",
        adapter=_SettingsAdapter(),
        prompt="probe",
        workspace=tmp_path,
        model="Ornith",
    )

    assert prepared.command.count("--settings") == 1
    assert _claude_settings(prepared.command)["allowedTools"][0] == "Bash"
    assert "Read" in _claude_settings(prepared.command)["allowedTools"]


def test_other_harness_process_preserves_ambient_environment(monkeypatch, tmp_path):
    _patch_boundary(monkeypatch)

    prepared = prepare_harness_process(
        adapter_name="hermes",
        adapter=_Adapter(),
        prompt="probe",
        workspace=tmp_path,
        model="Ornith",
    )

    assert prepared.environment["HOME"] == "/home/real-user"
    assert prepared.environment["OPENCODE_CONFIG_DIR"] == "/home/real-user/.opencode"
    assert prepared.environment["GOOSE_PATH_ROOT"] == "/home/real-user/.config/goose"
    assert "--settings" not in prepared.command
