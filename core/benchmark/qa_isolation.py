from __future__ import annotations

import json
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .paths import REPO_ROOT, RESULTS_ROOT
from .pristine_verifier import VerifierExecution, run_pristine_verifier
from .sandbox import SandboxPlan, workspace_sandbox


ISOLATION_EVIDENCE_SCHEMA = "aios-bench/qa-isolation-evidence/v1"
WORKSPACE_ISOLATION_EVIDENCE_SCHEMA = "aios-bench/qa-workspace-isolation-evidence/v1"
COMBINED_ISOLATION_EVIDENCE_SCHEMA = "aios-bench/qa-isolation-boundaries/v1"
_PROBE_FILE = "isolation_probe.json"
_WORKSPACE_PROBE_FILE = "workspace_isolation_probe.json"


def assess_strong_isolation(
    execution: VerifierExecution,
    probe: Mapping[str, Any] | None,
) -> dict[str, Any]:
    observed = dict(probe or {})
    workspace_write_verified = observed.get("workspace_write_verified") is True
    external_secret_unreadable = observed.get("external_secret_readable") is False
    host_loopback_unreachable = observed.get("host_loopback_reachable") is False
    strong_boundary_reported = bool(
        execution.isolation_strategy == "bubblewrap_minimal_runtime"
        and execution.filesystem_confined
        and execution.network_confined
    )
    ok = bool(
        execution.returncode == 0
        and strong_boundary_reported
        and workspace_write_verified
        and external_secret_unreadable
        and host_loopback_unreachable
    )
    return {
        "schema": ISOLATION_EVIDENCE_SCHEMA,
        "ok": ok,
        "strong_boundary_available": strong_boundary_reported,
        "isolation_strategy": execution.isolation_strategy,
        "filesystem_confined": execution.filesystem_confined,
        "network_confined": execution.network_confined,
        "isolation_error": execution.isolation_error,
        "verifier_returncode": execution.returncode,
        "workspace_write_verified": workspace_write_verified,
        "external_secret_unreadable": external_secret_unreadable,
        "host_loopback_unreachable": host_loopback_unreachable,
        "probe": observed,
    }


def assess_workspace_isolation(
    plan: SandboxPlan,
    *,
    returncode: int,
    probe: Mapping[str, Any] | None,
    execution_error: str | None = None,
) -> dict[str, Any]:
    """Assess the local-harness workspace boundary without inventing network claims."""
    observed = dict(probe or {})
    workspace_write_verified = observed.get("workspace_write_verified") is True
    grader_path_hidden = observed.get("grader_path_visible") is False
    expected_boundary = bool(
        plan.strategy == "bubblewrap_repo_hidden_workspace_only"
        and plan.write_confined
        and plan.grader_hidden
    )
    ok = bool(
        returncode == 0
        and execution_error is None
        and expected_boundary
        and workspace_write_verified
        and grader_path_hidden
    )
    return {
        "schema": WORKSPACE_ISOLATION_EVIDENCE_SCHEMA,
        "ok": ok,
        "strong_boundary_available": expected_boundary,
        "isolation_strategy": plan.strategy,
        "write_confined": plan.write_confined,
        "grader_hidden": plan.grader_hidden,
        "network_isolation_claimed": False,
        "isolation_error": execution_error or plan.isolation_error,
        "sandbox_returncode": returncode,
        "workspace_write_verified": workspace_write_verified,
        "grader_path_hidden": grader_path_hidden,
        "probe": observed,
    }


def _unavailable_evidence(exc: BaseException) -> dict[str, Any]:
    return {
        "schema": ISOLATION_EVIDENCE_SCHEMA,
        "ok": False,
        "strong_boundary_available": False,
        "isolation_strategy": None,
        "filesystem_confined": False,
        "network_confined": False,
        "isolation_error": f"{type(exc).__name__}: {exc}",
        "verifier_returncode": None,
        "workspace_write_verified": False,
        "external_secret_unreadable": False,
        "host_loopback_unreachable": False,
        "probe": {},
    }


def _unavailable_workspace_evidence(exc: BaseException) -> dict[str, Any]:
    return {
        "schema": WORKSPACE_ISOLATION_EVIDENCE_SCHEMA,
        "ok": False,
        "strong_boundary_available": False,
        "isolation_strategy": None,
        "write_confined": False,
        "grader_hidden": False,
        "network_isolation_claimed": False,
        "isolation_error": f"{type(exc).__name__}: {exc}",
        "sandbox_returncode": None,
        "workspace_write_verified": False,
        "grader_path_hidden": False,
        "probe": {},
    }


def _read_probe(path: Path) -> Mapping[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def run_strong_isolation_self_check() -> dict[str, Any]:
    """Exercise the real pristine-verifier boundary and return evidence."""
    with tempfile.TemporaryDirectory(prefix="aios-bench-isolation-qa-") as temporary:
        root = Path(temporary)
        pristine = root / "workspace"
        pristine.mkdir()
        secret = root / "host-secret.txt"
        secret.write_text("benchmark-host-secret\n", encoding="utf-8")

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = int(listener.getsockname()[1])
            code = (
                "import json, socket\n"
                "from pathlib import Path\n"
                f"secret = Path({str(secret)!r})\n"
                "external_secret_readable = False\n"
                "try:\n"
                "    secret.read_text(encoding='utf-8')\n"
                "except (OSError, PermissionError):\n"
                "    pass\n"
                "else:\n"
                "    external_secret_readable = True\n"
                "host_loopback_reachable = False\n"
                "try:\n"
                f"    connection = socket.create_connection(('127.0.0.1', {port}), timeout=0.5)\n"
                "except OSError:\n"
                "    pass\n"
                "else:\n"
                "    host_loopback_reachable = True\n"
                "    connection.close()\n"
                "probe = {\n"
                "    'workspace_write_verified': True,\n"
                "    'external_secret_readable': external_secret_readable,\n"
                "    'host_loopback_reachable': host_loopback_reachable,\n"
                "}\n"
                f"Path({_PROBE_FILE!r}).write_text(json.dumps(probe), encoding='utf-8')\n"
            )
            try:
                execution = run_pristine_verifier(
                    pristine,
                    code,
                    timeout=5.0,
                    mode="required",
                )
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                return _unavailable_evidence(exc)
        finally:
            listener.close()

        return assess_strong_isolation(execution, _read_probe(pristine / _PROBE_FILE))


def run_workspace_sandbox_self_check() -> dict[str, Any]:
    """Exercise the real local-harness workspace/grader boundary.

    This boundary intentionally does not claim network isolation. It proves that
    a representative local harness can write its current workspace while the
    benchmark repository/grader tree is hidden and host-persistent writes are
    confined to that workspace.
    """
    local_root = RESULTS_ROOT / ".local"
    local_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(
            prefix=".qa-workspace-sandbox-",
            dir=local_root,
        ) as temporary:
            workspace = Path(temporary) / "model" / "runs" / "run" / "workspaces" / "task"
            workspace.mkdir(parents=True)
            try:
                plan = workspace_sandbox("hermes", workspace, mode="required")
            except (OSError, RuntimeError) as exc:
                return _unavailable_workspace_evidence(exc)

            grader_path = (REPO_ROOT / "benchmarks").resolve()
            command = plan.wrap([
                "/bin/sh",
                "-c",
                (
                    "grader_visible=false; "
                    f"if [ -e {str(grader_path)!r} ]; then grader_visible=true; fi; "
                    f"printf '{{\"workspace_write_verified\":true,\"grader_path_visible\":%s}}' "
                    f"\"$grader_visible\" > {_WORKSPACE_PROBE_FILE!r}"
                ),
            ])
            try:
                process = subprocess.run(
                    command,
                    cwd=workspace,
                    text=True,
                    capture_output=True,
                    timeout=5.0,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return _unavailable_workspace_evidence(exc)

            error = None
            if process.returncode != 0:
                detail = (process.stderr or process.stdout).strip()[-1000:]
                error = detail or f"workspace sandbox probe exited {process.returncode}"
            return assess_workspace_isolation(
                plan,
                returncode=process.returncode,
                probe=_read_probe(workspace / _WORKSPACE_PROBE_FILE),
                execution_error=error,
            )
    except OSError as exc:
        return _unavailable_workspace_evidence(exc)


def run_isolation_boundary_self_checks() -> dict[str, Any]:
    pristine = run_strong_isolation_self_check()
    workspace = run_workspace_sandbox_self_check()
    return {
        "schema": COMBINED_ISOLATION_EVIDENCE_SCHEMA,
        "ok": bool(pristine["ok"] and workspace["ok"]),
        "pristine_verifier": pristine,
        "workspace_sandbox": workspace,
        "interpretation": (
            "The pristine verifier proves filesystem and network confinement; "
            "the workspace sandbox separately proves workspace write confinement "
            "and grader hiding and does not claim network isolation."
        ),
    }


def main() -> None:
    evidence = run_isolation_boundary_self_checks()
    print(json.dumps(evidence, indent=2, sort_keys=True))
    if not evidence["ok"]:
        raise SystemExit(2)


__all__ = [
    "COMBINED_ISOLATION_EVIDENCE_SCHEMA",
    "ISOLATION_EVIDENCE_SCHEMA",
    "WORKSPACE_ISOLATION_EVIDENCE_SCHEMA",
    "assess_strong_isolation",
    "assess_workspace_isolation",
    "run_isolation_boundary_self_checks",
    "run_strong_isolation_self_check",
    "run_workspace_sandbox_self_check",
]


if __name__ == "__main__":
    main()
