from __future__ import annotations

import importlib
import json

from core.benchmark.pristine_verifier import VerifierExecution


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
