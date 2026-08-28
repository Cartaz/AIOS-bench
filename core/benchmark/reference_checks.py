from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .reference_checks_core import CheckResult
from .reference_checks_data import check as check_data
from .reference_checks_knowledge import check as check_knowledge
from .reference_checks_long import check as check_long
from .reference_checks_subagents import check as check_subagents
from .reference_checks_system import check as check_system


def check_task(
    task_id: str,
    workspace: Path,
    fixture_root: Path,
    run_dir: Path | None = None,
    events: list[dict[str, Any]] | None = None,
) -> CheckResult:
    """Route one frozen reference oracle to its category implementation."""
    if task_id.startswith("knowledge_"):
        return check_knowledge(task_id, workspace, fixture_root)
    if task_id.startswith(("autonomy_", "coding_", "learning_")) or task_id == "tool_use_003":
        return check_data(task_id, workspace, fixture_root)
    if task_id.startswith("long_horizon_"):
        return check_long(task_id, workspace, fixture_root)

    if run_dir is None and os.environ.get("AIOS_BENCH_RUN_DIR"):
        run_dir = Path(os.environ["AIOS_BENCH_RUN_DIR"])
    if task_id.startswith("subagents_"):
        return check_subagents(
            task_id,
            workspace,
            fixture_root,
            run_dir,
            events=events or [],
        )
    return check_system(task_id, workspace, fixture_root, run_dir)
