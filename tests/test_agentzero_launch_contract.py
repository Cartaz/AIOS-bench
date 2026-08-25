from __future__ import annotations

import sys
from pathlib import Path

from core.benchmark.adapters import AgentZeroAdapter


def test_agentzero_uses_active_interpreter_and_canonical_package(tmp_path: Path) -> None:
    invocation = AgentZeroAdapter().build("prompt", tmp_path, "model")

    assert invocation.command[:3] == [
        sys.executable,
        "-m",
        "core.benchmark.agentzero_client",
    ]
    assert "aios_bench.agentzero_client" not in invocation.command
