from __future__ import annotations

from pathlib import Path

import pytest

from core.benchmark import pi_rpc


class _MissingPipesProcess:
    stdin = None
    stdout = None
    stderr = None


def test_pi_rpc_missing_stdio_pipes_fail_explicitly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    process = _MissingPipesProcess()
    cleaned: list[object] = []
    monkeypatch.setattr(pi_rpc, "spawn_owned", lambda *args, **kwargs: process)
    monkeypatch.setattr(pi_rpc, "terminate_owned", lambda value: cleaned.append(value))

    client = pi_rpc.PiRPCClient("model", tmp_path, timeout=1)
    with pytest.raises(RuntimeError, match="stdio pipes"):
        client.run("prompt")

    assert cleaned == [process]
