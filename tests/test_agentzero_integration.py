from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aios_bench.agentzero_client import normalize_log_items
from aios_bench.bubblewrap import BubblewrapCapability
from aios_bench.sandbox import workspace_sandbox
from aios_bench.telemetry import parse_output


# NOTE: This file intentionally exercises the Agent Zero integration through
# its public transport/adapter surface. Tests below use deterministic local
# stubs and do not require a running Agent Zero server.


def test_agentzero_jsonl_counts_as_non_inferred_delegation() -> None:
    raw = "\n".join(
        json.dumps(event)
        for event in normalize_log_items([
            {"type": "subagent", "id": "a"},
            {"type": "subagent", "id": "b"},
        ])
    )
    events = [event.to_dict() for event in parse_output(raw, source="agentzero")]
    starts = [event for event in events if event["type"] == "subagent_start"]
    assert len(starts) == 2
    assert all(not (event.get("data") or {}).get("inferred", False) for event in starts)


def test_agentzero_sandbox_adds_only_shared_projects_root_write_bridge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setattr("aios_bench.sandbox.shutil.which", lambda _: "/usr/bin/bwrap")
    monkeypatch.setattr(
        "aios_bench.sandbox.probe_bubblewrap",
        lambda executable: BubblewrapCapability(True),
    )

    plan = workspace_sandbox("agentzero", workspace)
    prefix = list(plan.command_prefix)
    bridge = str(projects_root.resolve())
    assert "agentzero_project_bridge" in plan.strategy
    pairs = list(zip(prefix, prefix[1:]))
    assert ("--bind", bridge) in pairs
    assert plan.write_confined is True
