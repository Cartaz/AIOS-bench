from __future__ import annotations

import json
import shutil
from pathlib import Path


# Dependency/cache directories that are reproducible and do not describe the
# agent's work. Keep generated deliverables and source files intact.
REPRODUCIBLE_DIRS = {
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def _load_statuses(checkpoint: Path) -> dict[str, str]:
    statuses: dict[str, str] = {}
    if not checkpoint.is_file():
        return statuses
    for line in checkpoint.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        task_id = item.get("task_id")
        if task_id:
            statuses[task_id] = str(item.get("status", "unknown"))
    return statuses


def _prune_reproducible_dirs(root: Path) -> int:
    removed = 0
    if not root.is_dir():
        return removed
    for path in root.rglob("*"):
        if path.is_dir() and path.name in REPRODUCIBLE_DIRS:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed


def prune_run_artifacts(run_dir: Path, *, keep_raw: bool = False) -> dict[str, int | bool]:
    """Keep the artifacts needed for post-run analysis and remove reproducible noise.

    The structured results.jsonl is the canonical trajectory record. Raw
    events.jsonl duplicates information already embedded in those results.
    For successful tasks, stdout is also redundant; for failures/timeouts it
    is retained because it is often the most useful diagnostic artifact.
    """
    if keep_raw or not run_dir.is_dir():
        return {"raw_kept": True, "files_removed": 0, "dirs_removed": 0}

    removed_files = 0
    removed_dirs = _prune_reproducible_dirs(run_dir / "workspaces")

    events = run_dir / "events.jsonl"
    if events.exists():
        events.unlink()
        removed_files += 1

    statuses = _load_statuses(run_dir / "results.jsonl")
    logs = run_dir / "logs"
    if logs.is_dir() and statuses:
        for path in logs.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if name.endswith(".stderr.log") and path.stat().st_size == 0:
                path.unlink()
                removed_files += 1
                continue
            if name.endswith(".stdout.log"):
                task_id = name.removesuffix(".stdout.log")
                if statuses.get(task_id) == "completed":
                    path.unlink()
                    removed_files += 1

    manifest = {
        "raw_kept": False,
        "canonical_results": "results.jsonl",
        "raw_event_stream_removed": True,
        "successful_stdout_removed": True,
        "failed_or_timeout_stdout_retained": True,
        "empty_stderr_removed": True,
        "reproducible_dependency_dirs_removed": sorted(REPRODUCIBLE_DIRS),
    }
    (run_dir / "retention.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {"raw_kept": False, "files_removed": removed_files, "dirs_removed": removed_dirs}
