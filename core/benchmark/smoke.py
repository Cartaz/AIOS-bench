from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .config import AGENTS
from .models import Task


SMOKE_SCHEMA = "aios-bench/harness-smoke/v1"
CORE_TASK_ID = "tool_use_001"
BROWSER_TASK_ID = "browser_001"
SUBAGENT_TASK_ID = "subagents_001"


def make_smoke_id() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S_%f_smoke")


def select_smoke_tasks(tasks: Iterable[Task], harnesses: Iterable[str]) -> list[Task]:
    """Return the smallest capability-aware Frontier v3 integration probe.

    Every harness executes one ordinary workspace/tool-use task. Browser and
    structured-subagent probes are included only when at least one selected
    harness claims the corresponding hard capability. In an ``--all`` run the
    other harnesses record those probes as expected ``unsupported`` results.
    """

    names = tuple(harnesses)
    by_id = {task.id: task for task in tasks}
    selected = [CORE_TASK_ID]
    if any(AGENTS[name].adapter.supports("browser") for name in names):
        selected.append(BROWSER_TASK_ID)
    if any(AGENTS[name].adapter.supports("structured_subagent_events") for name in names):
        selected.append(SUBAGENT_TASK_ID)

    missing = [task_id for task_id in selected if task_id not in by_id]
    if missing:
        raise ValueError("smoke profile is incompatible with this suite: " + ", ".join(missing))
    return [by_id[task_id] for task_id in selected]


def discover_smoke_run_dirs(output_root: Path, smoke_id: str) -> dict[str, list[Path]]:
    """Find only runs created by one smoke invocation.

    Smoke output is intentionally rooted outside ``results/.local``. Discovery
    uses run metadata rather than model-path naming, so model identifiers never
    need to be reconstructed by the diagnostic layer.
    """

    found: dict[str, list[Path]] = {}
    if not output_root.is_dir():
        return found
    for metadata_path in sorted(output_root.glob("*/*/runs/*/run.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        run_id = str(metadata.get("run_id") or "")
        if run_id != smoke_id and not run_id.startswith(smoke_id + "-r"):
            continue
        harness = str(metadata.get("harness") or "")
        if harness not in AGENTS:
            continue
        found.setdefault(harness, []).append(metadata_path.parent)
    for harness in found:
        found[harness].sort(key=lambda path: path.name)
    return found


def _latest_results(run_dir: Path) -> dict[str, dict]:
    checkpoint = run_dir / "results.jsonl"
    latest: dict[str, dict] = {}
    if not checkpoint.is_file():
        return latest
    for line in checkpoint.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        task_id = row.get("task_id")
        if task_id:
            latest[str(task_id)] = row
    return latest


def _event_counts(row: dict) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for event in row.get("events") or []:
        if isinstance(event, dict) and event.get("type"):
            counts[str(event["type"])] += 1
    return dict(sorted(counts.items()))


def build_smoke_report(
    run_dirs: dict[str, list[Path]],
    tasks: list[Task],
) -> dict:
    harness_reports: list[dict] = []
    integration_ok = bool(run_dirs)
    strict_model_ready = bool(run_dirs)
    server_metrics_ready = bool(run_dirs)

    for harness in sorted(run_dirs):
        adapter = AGENTS[harness].adapter
        runs: list[dict] = []
        for run_dir in run_dirs[harness]:
            metadata_path = run_dir / "run.json"
            metadata = (
                json.loads(metadata_path.read_text(encoding="utf-8"))
                if metadata_path.is_file()
                else {}
            )
            manifest = metadata.get("manifest") if isinstance(metadata.get("manifest"), dict) else {}
            model = manifest.get("model") if isinstance(manifest.get("model"), dict) else {}
            server_metrics = (
                manifest.get("server_metrics")
                if isinstance(manifest.get("server_metrics"), dict)
                else {}
            )
            latest = _latest_results(run_dir)
            requested = model.get("requested")
            resolved = model.get("resolved")
            model_binding_ok = bool(requested and resolved == requested)
            strict = bool(model.get("strictly_comparable"))
            metrics_enabled = bool(server_metrics.get("enabled"))
            strict_model_ready = strict_model_ready and strict
            server_metrics_ready = server_metrics_ready and metrics_enabled

            task_rows: list[dict] = []
            run_ok = model_binding_ok
            for task in tasks:
                assessment = adapter.assess_task(task)
                row = latest.get(task.id)
                if assessment.is_supported:
                    task_ok = bool(row and row.get("success"))
                else:
                    task_ok = bool(row and row.get("status") == "unsupported")
                run_ok = run_ok and task_ok
                task_rows.append({
                    "task_id": task.id,
                    "category": task.category,
                    "expected_supported": assessment.is_supported,
                    "status": row.get("status") if row else "missing",
                    "success": bool(row.get("success")) if row else False,
                    "score": row.get("score") if row else None,
                    "failure_kind": row.get("failure_kind") if row else None,
                    "telemetry_available": bool(row.get("telemetry_available")) if row else False,
                    "event_counts": _event_counts(row or {}),
                    "ok": task_ok,
                })

            integration_ok = integration_ok and run_ok
            runs.append({
                "run_id": metadata.get("run_id", run_dir.name),
                "run_dir": str(run_dir),
                "model": {
                    "requested": requested,
                    "resolved": resolved,
                    "resolution": model.get("resolution"),
                    "verification": model.get("verification"),
                    "binding_ok": model_binding_ok,
                    "strictly_comparable": strict,
                },
                "server_metrics_enabled": metrics_enabled,
                "tasks": task_rows,
                "ok": run_ok,
            })
        harness_reports.append({"harness": harness, "runs": runs, "ok": bool(runs) and all(run["ok"] for run in runs)})

    return {
        "schema": SMOKE_SCHEMA,
        "suite": "frontier_v3",
        "task_ids": [task.id for task in tasks],
        "integration_ok": integration_ok,
        "strict_model_ready": strict_model_ready,
        "server_metrics_ready": server_metrics_ready,
        "harnesses": harness_reports,
    }


def write_smoke_report(
    output_root: Path,
    smoke_id: str,
    run_dirs: dict[str, list[Path]],
    tasks: list[Task],
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"{smoke_id}.json"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(build_smoke_report(run_dirs, tasks), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path
