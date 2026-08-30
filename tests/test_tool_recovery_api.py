from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from aios_bench.parametric import materialize_variant
from aios_bench.tool_recovery_api import start_tool_recovery_runtime


def _client(
    workspace: Path,
    environment: dict[str, str],
    *args: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(environment)
    env["AIOS_BENCH_WORKSPACE"] = str(workspace)
    return subprocess.run(
        [sys.executable, str(workspace / "tools" / "tool_api.py"), *args],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


def test_generated_client_reaches_authenticated_tool_runtime(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("tool_recovery", workspace, seed=91)
    runtime = start_tool_recovery_runtime(
        workspace,
        run_dir,
        "tool_recovery_001",
        oracle,
    )
    try:
        schema = _client(workspace, runtime.environment, "schema")
        assert schema.returncode == 0, schema.stderr
        contract = json.loads(schema.stdout)
        active = {
            item["name"]
            for item in contract["tools"]
            if item.get("lifecycle") == "active"
        }
        assert active == {"cases.list", "cases.get", "actions.process"}

        listing = _client(
            workspace,
            runtime.environment,
            "invoke",
            "cases.list",
            "--args",
            "{}",
        )
        assert listing.returncode == 0, listing.stderr
        payload = json.loads(listing.stdout)
        assert len(payload["cases"]) == oracle["parameters"]["case_count"]
        assert any(item["complete"] is False for item in payload["cases"])
    finally:
        runtime.close()

    assert (workspace / oracle["state_path"]).is_file()
