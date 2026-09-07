from pathlib import Path

from aios_bench.adapters import Adapter, AgentInvocation
from aios_bench.harness_process import prepare_harness_process
from aios_bench.sandbox import SandboxPlan


class _Adapter(Adapter):
    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        return AgentInvocation(
            ["fake-harness", prompt],
            {"AIOS_BENCH_WORKSPACE": str(workspace), "HOME": "/home/real-user"},
        )


def _patch_boundary(monkeypatch):
    monkeypatch.setattr(
        "aios_bench.harness_process.with_project_bin",
        lambda: {"PATH": "/usr/bin", "HOME": "/home/real-user"},
    )
    monkeypatch.setattr(
        "aios_bench.harness_process.workspace_sandbox",
        lambda adapter_name, workspace: SandboxPlan("test"),
    )


def test_claude_process_uses_temporary_home(monkeypatch, tmp_path):
    _patch_boundary(monkeypatch)

    prepared = prepare_harness_process(
        adapter_name="claude",
        adapter=_Adapter(),
        prompt="probe",
        workspace=tmp_path,
        model="Ornith",
    )

    assert prepared.environment["HOME"] == "/tmp"


def test_other_harness_process_preserves_home(monkeypatch, tmp_path):
    _patch_boundary(monkeypatch)

    prepared = prepare_harness_process(
        adapter_name="hermes",
        adapter=_Adapter(),
        prompt="probe",
        workspace=tmp_path,
        model="Ornith",
    )

    assert prepared.environment["HOME"] == "/home/real-user"
