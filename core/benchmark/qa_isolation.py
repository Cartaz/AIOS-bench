from __future__ import annotations

import json
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .pristine_verifier import VerifierExecution, run_pristine_verifier


ISOLATION_EVIDENCE_SCHEMA = "aios-bench/qa-isolation-evidence/v1"
_PROBE_FILE = "isolation_probe.json"


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


def run_strong_isolation_self_check() -> dict[str, Any]:
    """Exercise the real verifier boundary and return machine-readable evidence.

    The check is fail-closed: it explicitly requests the strong verifier mode.
    It proves that the sandbox can write its submitted workspace while a sibling
    host secret and a host loopback listener remain unreachable.
    """
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

        probe_path = pristine / _PROBE_FILE
        try:
            raw_probe = json.loads(probe_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw_probe = None
        probe = raw_probe if isinstance(raw_probe, Mapping) else None
        return assess_strong_isolation(execution, probe)


def main() -> None:
    evidence = run_strong_isolation_self_check()
    print(json.dumps(evidence, indent=2, sort_keys=True))
    if not evidence["ok"]:
        raise SystemExit(2)


__all__ = [
    "ISOLATION_EVIDENCE_SCHEMA",
    "assess_strong_isolation",
    "run_strong_isolation_self_check",
]


if __name__ == "__main__":
    main()
