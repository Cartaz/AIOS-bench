from pathlib import Path

from core.benchmark.frontier_v3_runner import FrontierV3Runner
from core.benchmark.frontier_v4_runner import FrontierV4Runner
from core.benchmark.runner import AGENTS


ROOT = Path(__file__).resolve().parents[1]


def _assert_resource_wiring(runner, interval: float) -> None:
    assert runner.resource_poll_interval == interval
    assert runner.execution_manifest["client_resources"]["poll_interval_seconds"] == interval


def test_frontier_v3_wrapper_forwards_resource_poll_interval(tmp_path: Path) -> None:
    runner = FrontierV3Runner(
        ROOT,
        AGENTS["piagent"],
        tmp_path / "v3",
        task_timeout=1,
        total_timeout=None,
        model="test",
        run_id="v3-resource-wiring",
        resource_poll_interval=0.75,
    )
    _assert_resource_wiring(runner, 0.75)


def test_frontier_v4_wrapper_forwards_resource_poll_interval(tmp_path: Path) -> None:
    runner = FrontierV4Runner(
        ROOT,
        AGENTS["piagent"],
        tmp_path / "v4",
        task_timeout=1,
        total_timeout=None,
        model="test",
        run_id="v4-resource-wiring",
        resource_poll_interval=0.5,
    )
    _assert_resource_wiring(runner, 0.5)
