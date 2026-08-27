from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.request import urlopen

import pytest

from core.benchmark.frontier_v4_runner import FrontierV4Runner
from core.benchmark.materialization import ParametricTaskMaterializer
from core.benchmark.parametric.runtime_investigation import (
    RuntimeInvestigationPressure,
    check_runtime_investigation_variant,
    generate_runtime_investigation_variant,
    runtime_probe_payload,
)
from core.benchmark.runner import AGENTS
from core.benchmark.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"


def _repair_from_probe(workspace: Path, payload: dict) -> None:
    routes_path = workspace / "config" / "routes.json"
    routes = json.loads(routes_path.read_text(encoding="utf-8"))
    routes[payload["active_lane"]] = int(payload["expected_backend_port"])
    routes_path.write_text(json.dumps(routes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = workspace / "reports" / "runtime_probe.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def test_runtime_variant_forces_stale_static_hint_to_disagree_with_live_state(tmp_path: Path) -> None:
    oracle = generate_runtime_investigation_variant(
        tmp_path,
        seed=72,
        pressure=RuntimeInvestigationPressure(lanes=5, distractor_docs=2),
    )

    assert oracle["active_lane"] != oracle["stale_lane"]
    assert oracle["active_lane"] in oracle["lanes"]
    assert oracle["stale_lane"] in oracle["lanes"]
    assert runtime_probe_payload(oracle)["active_lane"] == oracle["active_lane"]


def test_correct_route_without_runtime_evidence_does_not_pass(tmp_path: Path) -> None:
    oracle = generate_runtime_investigation_variant(
        tmp_path,
        seed=73,
        pressure=RuntimeInvestigationPressure(),
    )
    routes_path = tmp_path / "config" / "routes.json"
    routes = json.loads(routes_path.read_text(encoding="utf-8"))
    routes[oracle["active_lane"]] = oracle["backend_port"]
    routes_path.write_text(json.dumps(routes, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    passed, detail = check_runtime_investigation_variant(tmp_path, oracle)

    assert passed is False
    assert "evidence missing" in detail


def test_runtime_probe_exposes_hidden_live_state_and_is_cleaned_up(tmp_path: Path) -> None:
    task = SimpleNamespace(
        id="runtime-test",
        acceptance=({"type": "parametric_reference", "family": "runtime_investigation"},),
    )
    runner = SimpleNamespace(repo_root=ROOT, run_dir=tmp_path / "run")
    materializer = ParametricTaskMaterializer(base_seed=42)

    workspace = materializer.prepare(runner, task)
    process = materializer._runtime_processes[task.id]
    try:
        endpoint = json.loads((workspace / "runtime" / "endpoint.json").read_text(encoding="utf-8"))
        with urlopen(endpoint["state_url"], timeout=2) as response:  # noqa: S310 - loopback test fixture
            payload = json.loads(response.read().decode("utf-8"))
        oracle = materializer._variants[task.id]

        assert payload == runtime_probe_payload(oracle)
        assert payload["active_lane"] != oracle["stale_lane"]
        _repair_from_probe(workspace, payload)
        passed, detail = check_runtime_investigation_variant(workspace, oracle)
        assert passed is True, detail
    finally:
        materializer.after_task(runner, task)

    assert process.poll() is not None


def test_editing_inactive_lane_is_rejected_even_with_valid_probe_report(tmp_path: Path) -> None:
    oracle = generate_runtime_investigation_variant(
        tmp_path,
        seed=74,
        pressure=RuntimeInvestigationPressure(),
    )
    payload = runtime_probe_payload(oracle)
    _repair_from_probe(tmp_path, payload)
    inactive = next(lane for lane in oracle["lanes"] if lane != oracle["active_lane"])
    routes_path = tmp_path / "config" / "routes.json"
    routes = json.loads(routes_path.read_text(encoding="utf-8"))
    routes[inactive] += 1
    routes_path.write_text(json.dumps(routes, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    passed, detail = check_runtime_investigation_variant(tmp_path, oracle)

    assert passed is False
    assert "inactive lane" in detail


def test_runner_cleans_runtime_probe_when_task_execution_raises(monkeypatch, tmp_path: Path) -> None:
    task = next(
        item
        for item in load_tasks(TASK_ROOT, "frontier_v4")
        if item.id == "autonomy_runtime_investigation_001"
    )
    runner = FrontierV4Runner(
        ROOT,
        AGENTS["piagent"],
        tmp_path / "results",
        task_timeout=1,
        total_timeout=None,
        model="test",
        run_id="runtime-cleanup",
    )
    captured: dict[str, object] = {}

    def fail_after_materialization(active_runner, active_task, timeout):
        active_runner._workspace(active_task)
        captured["process"] = active_runner.suite.materializer._runtime_processes[active_task.id]
        raise RuntimeError("synthetic task failure")

    owner_module = sys.modules[runner.run_task.__func__.__module__]
    monkeypatch.setattr(owner_module, "run_frontier_task", fail_after_materialization)

    with pytest.raises(RuntimeError, match="synthetic task failure"):
        runner.run_task(task, 1)

    process = captured["process"]
    assert process.poll() is not None
    assert task.id not in runner.suite.materializer._runtime_processes
