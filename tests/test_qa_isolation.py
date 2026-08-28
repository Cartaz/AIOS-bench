from __future__ import annotations

import importlib
import json
import subprocess
from types import SimpleNamespace

from core.benchmark.pristine_verifier import VerifierExecution
from core.benchmark.sandbox import SandboxPlan


qa_isolation = importlib.import_module("core.benchmark.qa_isolation")


def _execution(**overrides) -> VerifierExecution:
    values = {
        "returncode": 0,
        "stdout": "",
        "stderr": "",
        "isolation_strategy": "bubblewrap_minimal_runtime",
        "filesystem_confined": True,
        "network_confined": True,
        "isolation_error": None,
    }
    values.update(overrides)
    return VerifierExecution(**values)


def _workspace_plan(**overrides) -> SandboxPlan:
    values = {
        "strategy": "bubblewrap_repo_hidden_workspace_only",
        "command_prefix": ("bwrap", "--"),
        "write_confined": True,
        "grader_hidden": True,
        "isolation_error": None,
    }
    values.update(overrides)
    return SandboxPlan(**values)


def test_assessment_requires_all_strong_isolation_observations() -> None:
    probe = {
        "workspace_write_verified": True,
        "external_secret_readable": False,
        "host_loopback_reachable": False,
    }

    result = qa_isolation.assess_strong_isolation(_execution(), probe)

    assert result["schema"] == "aios-bench/qa-isolation-evidence/v1"
    assert result["ok"] is True
    assert result["strong_boundary_available"] is True
    assert result["external_secret_unreadable"] is True
    assert result["host_loopback_unreachable"] is True


def test_assessment_rejects_unconfined_strategy_even_with_good_probe() -> None:
    probe = {
        "workspace_write_verified": True,
        "external_secret_readable": False,
        "host_loopback_reachable": False,
    }

    result = qa_isolation.assess_strong_isolation(
        _execution(
            isolation_strategy="isolated_python_unconfined",
            filesystem_confined=False,
            network_confined=False,
        ),
        probe,
    )

    assert result["ok"] is False
    assert result["strong_boundary_available"] is False


def test_workspace_assessment_requires_write_confinement_and_grader_hiding() -> None:
    probe = {
        "workspace_write_verified": True,
        "grader_path_visible": False,
    }

    result = qa_isolation.assess_workspace_isolation(
        _workspace_plan(),
        returncode=0,
        probe=probe,
    )

    assert result["schema"] == "aios-bench/qa-workspace-isolation-evidence/v1"
    assert result["ok"] is True
    assert result["write_confined"] is True
    assert result["grader_hidden"] is True
    assert result["grader_path_hidden"] is True
    assert result["network_isolation_claimed"] is False


def test_workspace_assessment_rejects_writable_bridge_plan() -> None:
    probe = {
        "workspace_write_verified": True,
        "grader_path_visible": False,
    }

    result = qa_isolation.assess_workspace_isolation(
        _workspace_plan(
            strategy="bubblewrap_remote_transport_grader_hidden_agentzero_project_bridge",
            write_confined=False,
        ),
        returncode=0,
        probe=probe,
    )

    assert result["ok"] is False
    assert result["strong_boundary_available"] is False
    assert result["network_isolation_claimed"] is False


def test_self_check_reports_required_mode_unavailable_without_claiming_confinement(monkeypatch) -> None:
    def unavailable(*args, **kwargs):
        raise RuntimeError("namespaces denied")

    monkeypatch.setattr(qa_isolation, "run_pristine_verifier", unavailable)

    result = qa_isolation.run_strong_isolation_self_check()

    assert result["ok"] is False
    assert result["strong_boundary_available"] is False
    assert result["filesystem_confined"] is False
    assert result["network_confined"] is False
    assert "namespaces denied" in result["isolation_error"]


def test_self_check_turns_verifier_timeout_into_failed_evidence(monkeypatch) -> None:
    def timed_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(["bwrap"], 5)

    monkeypatch.setattr(qa_isolation, "run_pristine_verifier", timed_out)

    result = qa_isolation.run_strong_isolation_self_check()

    assert result["ok"] is False
    assert result["strong_boundary_available"] is False
    assert "TimeoutExpired" in result["isolation_error"]


def test_self_check_reads_probe_created_inside_pristine_workspace(monkeypatch) -> None:
    def confined(pristine, code, *, timeout, mode):
        assert timeout == 5.0
        assert mode == "required"
        (pristine / "isolation_probe.json").write_text(
            json.dumps({
                "workspace_write_verified": True,
                "external_secret_readable": False,
                "host_loopback_reachable": False,
            }),
            encoding="utf-8",
        )
        return _execution()

    monkeypatch.setattr(qa_isolation, "run_pristine_verifier", confined)

    result = qa_isolation.run_strong_isolation_self_check()

    assert result["ok"] is True
    assert result["probe"]["workspace_write_verified"] is True


def test_workspace_self_check_reports_required_mode_unavailable(monkeypatch) -> None:
    def unavailable(*args, **kwargs):
        raise RuntimeError("workspace namespaces denied")

    monkeypatch.setattr(qa_isolation, "workspace_sandbox", unavailable)

    result = qa_isolation.run_workspace_sandbox_self_check()

    assert result["ok"] is False
    assert result["write_confined"] is False
    assert result["grader_hidden"] is False
    assert result["network_isolation_claimed"] is False
    assert "workspace namespaces denied" in result["isolation_error"]


def test_workspace_self_check_reads_probe_from_real_workspace_path(monkeypatch) -> None:
    monkeypatch.setattr(
        qa_isolation,
        "workspace_sandbox",
        lambda adapter, workspace, mode: _workspace_plan(),
    )

    def completed(command, *, cwd, text, capture_output, timeout, check):
        assert timeout == 5.0
        assert text is True
        assert capture_output is True
        assert check is False
        (cwd / "workspace_isolation_probe.json").write_text(
            json.dumps({
                "workspace_write_verified": True,
                "grader_path_visible": False,
            }),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(qa_isolation.subprocess, "run", completed)

    result = qa_isolation.run_workspace_sandbox_self_check()

    assert result["ok"] is True
    assert result["grader_path_hidden"] is True
    assert result["network_isolation_claimed"] is False


def test_combined_isolation_requires_both_boundaries(monkeypatch) -> None:
    monkeypatch.setattr(
        qa_isolation,
        "run_strong_isolation_self_check",
        lambda: {"ok": True, "schema": "pristine"},
    )
    monkeypatch.setattr(
        qa_isolation,
        "run_workspace_sandbox_self_check",
        lambda: {"ok": False, "schema": "workspace"},
    )

    result = qa_isolation.run_isolation_boundary_self_checks()

    assert result["schema"] == "aios-bench/qa-isolation-boundaries/v1"
    assert result["ok"] is False
    assert result["pristine_verifier"]["ok"] is True
    assert result["workspace_sandbox"]["ok"] is False
    assert "does not claim network isolation" in result["interpretation"]
