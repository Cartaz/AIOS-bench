from __future__ import annotations

from pathlib import Path


BENCHMARK_PACKAGE_ROOT = Path(__file__).resolve().parent
CORE_ROOT = BENCHMARK_PACKAGE_ROOT.parent
REPO_ROOT = CORE_ROOT.parent
TASKS_ROOT = REPO_ROOT / "benchmarks" / "tasks"
RESULTS_ROOT = REPO_ROOT / "results"


def assert_repository_layout() -> None:
    """Fail clearly if the benchmark package is detached from its repository data."""
    if not TASKS_ROOT.is_dir():
        raise RuntimeError(f"Benchmark task catalog not found at {TASKS_ROOT}")
