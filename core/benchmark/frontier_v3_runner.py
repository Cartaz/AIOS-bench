from __future__ import annotations

from pathlib import Path

from .frontier_runner import FrontierRunner
from .suites import frontier_v3_suite


class FrontierV3Runner(FrontierRunner):
    """Compatibility constructor for the frozen Frontier v3 catalog."""

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
    ) -> None:
        super().__init__(
            repo_root,
            agent,
            results_dir,
            task_timeout,
            total_timeout,
            suite=frontier_v3_suite(),
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
