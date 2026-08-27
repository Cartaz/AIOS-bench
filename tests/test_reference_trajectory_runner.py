from __future__ import annotations

from pathlib import Path

from aios_bench.frontier_v4_runner import FrontierV4Runner
from aios_bench.runner import AGENTS
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]


def test_frontier_runner_persists_reference_trajectory_without_touching_score(tmp_path: Path) -> None:
    runner = FrontierV4Runner(
        ROOT,
        AGENTS["piagent"],
        tmp_path / "results",
        task_timeout=1,
        total_timeout=None,
        model="test",
        run_id="reference-trajectory",
    )
    task = next(
        item
        for item in load_tasks(ROOT / "benchmarks" / "tasks", "frontier_v4")
        if item.id == "greenfield_registry_001"
    )
    item = {
        **runner._result_identity(task),
        "agent": runner.agent.name,
        "success": True,
        "status": "completed",
        "score": 100.0,
        "events": [
            {"type": "file_read", "source": "piagent", "sequence": 1, "data": {}},
            {"type": "file_write", "source": "piagent", "sequence": 2, "data": {}},
            {"type": "tool_call", "source": "piagent", "sequence": 3, "data": {"tool": "terminal"}},
        ],
    }

    runner._write_result(item)
    persisted = runner.latest_results()[task.id]

    assert persisted["score"] == 100.0
    assert persisted["success"] is True
    assert persisted["reference_trajectory"]["available"] is True
    assert persisted["reference_trajectory"]["complete"] is True
    assert persisted["reference_trajectory"]["affects_score"] is False
