from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .frontier_runner import FrontierRunner
from .suites import frontier_v4_suite


class FrontierV4Runner(FrontierRunner):
    """Compatibility constructor for the parametric Frontier v4 catalog."""

    def __init__(
        self,
        repo_root: Path,
        agent,
        results_dir: Path,
        task_timeout: float,
        total_timeout: float | None,
        resume: bool = True,
        model: str = "unknown",
        keep_raw: bool = False,
        run_id: str | None = None,
        server_metrics_url: str | None = None,
        server_metrics_model: str | None = None,
        server_resource_url: str | None = None,
        max_output_tokens: int = 65536,
        metrics_poll_interval: float = 1.0,
        resource_poll_interval: float = 1.0,
        variant_base_seed: int = 42,
        parametric_parameters: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            repo_root,
            agent,
            results_dir,
            task_timeout,
            total_timeout,
            suite=frontier_v4_suite(
                variant_base_seed=variant_base_seed,
                parametric_parameters=parametric_parameters,
            ),
            resume=resume,
            model=model,
            keep_raw=keep_raw,
            run_id=run_id,
            server_metrics_url=server_metrics_url,
            server_metrics_model=server_metrics_model,
            server_resource_url=server_resource_url,
            max_output_tokens=max_output_tokens,
            metrics_poll_interval=metrics_poll_interval,
            resource_poll_interval=resource_poll_interval,
        )

    def _task_seed(self, task) -> int:
        return self.suite.materializer.task_seed(task)
