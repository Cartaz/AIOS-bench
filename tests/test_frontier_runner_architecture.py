from __future__ import annotations

from pathlib import Path

from core.benchmark.frontier_runner import FrontierRunner
from core.benchmark.frontier_v3_runner import FrontierV3Runner, frontier_v3_suite
from core.benchmark.frontier_v4_runner import FrontierV4Runner, frontier_v4_suite
from core.benchmark.materialization import ParametricTaskMaterializer, StaticTaskMaterializer
from core.run_service import BenchmarkService, ObservableFrontierRunner, RunRequest

ROOT = Path(__file__).resolve().parents[1]


def test_frontier_versions_share_one_execution_engine() -> None:
    assert issubclass(FrontierV3Runner, FrontierRunner)
    assert issubclass(FrontierV4Runner, FrontierRunner)
    assert isinstance(frontier_v3_suite().materializer, StaticTaskMaterializer)
    assert isinstance(frontier_v4_suite().materializer, ParametricTaskMaterializer)


def test_desktop_service_uses_same_runner_type_for_v3_and_v4(tmp_path: Path) -> None:
    service = BenchmarkService(ROOT)
    common = dict(
        harnesses=("piagent",),
        task_ids=("autonomy_001",),
        model="test",
        task_timeout=1,
    )
    v3 = RunRequest(suite="frontier_v3", **common)
    runner_v3 = service._build_runner(v3, "piagent", "v3-test", 42, lambda event: None)

    v4 = RunRequest(
        suite="frontier_v4",
        harnesses=("piagent",),
        task_ids=("autonomy_expense_001",),
        model="test",
        task_timeout=1,
    )
    runner_v4 = service._build_runner(v4, "piagent", "v4-test", 42, lambda event: None)

    assert type(runner_v3) is ObservableFrontierRunner
    assert type(runner_v4) is ObservableFrontierRunner
    assert runner_v3.suite.name == "frontier_v3"
    assert runner_v4.suite.name == "frontier_v4"
