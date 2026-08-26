from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable


ResourceKey = tuple[str, str, str, str, str]


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _matches_suite(row: dict[str, Any], suite: str | None, suite_revision: str | None) -> bool:
    if suite is not None and str(row.get("suite")) != suite:
        return False
    if suite_revision is not None and str(row.get("suite_revision")) != suite_revision:
        return False
    return True


def _identity(row: dict[str, Any]) -> ResourceKey:
    return (
        str(row.get("harness", row.get("agent", "unknown"))),
        str(row.get("model", "unknown")),
        str(row.get("suite", "legacy")),
        str(row.get("suite_revision", "legacy")),
        str(row.get("execution_fingerprint", "unreported")),
    )


def _values(items: list[dict[str, Any]], path: tuple[str, ...]) -> list[float]:
    values: list[float] = []
    for item in items:
        current: Any = item
        for part in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(part)
        number = _number(current)
        if number is not None:
            values.append(number)
    return values


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _maximum(values: list[float]) -> float | None:
    return max(values) if values else None


def _resource_side(items: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
    resources = [
        item[field]
        for item in items
        if isinstance(item.get(field), dict) and item[field].get("available") is True
    ]
    if not resources:
        return None

    rss_baseline = _values(resources, ("process_tree", "rss_baseline_bytes"))
    rss_peak = _values(resources, ("process_tree", "rss_peak_bytes"))
    rss_delta = _values(resources, ("process_tree", "rss_peak_delta_bytes"))
    cpu_mean = _values(resources, ("process_tree", "cpu_mean_percent"))
    vram_baseline = _values(resources, ("process_tree", "vram_baseline_bytes"))
    vram_peak = _values(resources, ("process_tree", "vram_peak_bytes"))
    vram_delta = _values(resources, ("process_tree", "vram_peak_delta_bytes"))
    gpu_mean = _values(resources, ("process_tree", "gpu_engine_time_mean_percent"))
    host_ram_delta = _values(resources, ("host", "ram_peak_delta_bytes"))
    host_vram_delta = _values(resources, ("gpu", "vram_peak_delta_bytes"))

    return {
        "measured_tasks": len(resources),
        "rss_baseline_task_mean_bytes": _mean(rss_baseline),
        "rss_peak_task_mean_bytes": _mean(rss_peak),
        "rss_peak_max_bytes": _maximum(rss_peak),
        "rss_peak_delta_task_mean_bytes": _mean(rss_delta),
        "rss_peak_delta_max_bytes": _maximum(rss_delta),
        "cpu_task_mean_percent": _mean(cpu_mean),
        "vram_attributed_tasks": len(vram_peak),
        "vram_baseline_task_mean_bytes": _mean(vram_baseline),
        "vram_peak_task_mean_bytes": _mean(vram_peak),
        "vram_peak_max_bytes": _maximum(vram_peak),
        "vram_peak_delta_task_mean_bytes": _mean(vram_delta),
        "vram_peak_delta_max_bytes": _maximum(vram_delta),
        "gpu_engine_time_task_mean_percent": _mean(gpu_mean),
        "host_ram_peak_delta_task_mean_bytes": _mean(host_ram_delta),
        "host_vram_peak_delta_task_mean_bytes": _mean(host_vram_delta),
    }


def resource_efficiency_groups(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate client and inference-server resource cost without affecting score.

    Resource observations are grouped by the same execution identity used by the
    other benchmark statistics. Peak values are never summed across tasks: the
    report exposes a task-mean peak and the maximum observed peak separately.
    """
    grouped: dict[ResourceKey, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not _matches_suite(row, suite, suite_revision):
            continue
        if row.get("status") == "unsupported" or row.get("comparable") is False:
            continue
        client = row.get("client_resources")
        server = row.get("server_resources")
        if not (
            isinstance(client, dict) and client.get("available") is True
            or isinstance(server, dict) and server.get("available") is True
        ):
            continue
        grouped[_identity(row)].append(row)

    result: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        client = _resource_side(items, "client_resources")
        server = _resource_side(items, "server_resources")
        result.append({
            "harness": key[0],
            "model": key[1],
            "suite": key[2],
            "suite_revision": key[3],
            "execution_fingerprint": key[4],
            "client": client,
            "server": server,
        })
    return result
