from __future__ import annotations

from pathlib import Path

from core.benchmark.local_gateway import write_pi_profile
from core.benchmark.sandbox import _pi_profile_args


def test_pi_gateway_profile_is_bound_read_only(tmp_path: Path):
    workspace = tmp_path / "runs" / "run-1" / "workspaces" / "task-1"
    workspace.mkdir(parents=True)
    profile = write_pi_profile(
        workspace,
        endpoint="http://127.0.0.1:8080/v1",
        model="Ornith",
    )

    args = _pi_profile_args(workspace)
    assert "--ro-bind" in args
    bind_index = args.index("--ro-bind")
    assert args[bind_index + 1] == str(profile.resolve())
    assert args[bind_index + 2] == str(profile.resolve())
    assert str(workspace) not in str(profile)
