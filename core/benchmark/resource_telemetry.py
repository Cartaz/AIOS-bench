from __future__ import annotations

import math
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import psutil


@dataclass(frozen=True)
class ResourceSnapshot:
    captured_at: float
    process_rss_bytes: int
    process_cpu_percent: float
    process_count: int
    host_cpu_percent: float
    host_ram_used_bytes: int
    gpu_busy_percent: float | None = None
    vram_used_bytes: int | None = None
    vram_total_bytes: int | None = None
    gpu_device_count: int = 0


@dataclass
class _ProcessCpuState:
    captured_at: float | None = None
    cpu_seconds: dict[tuple[int, float], float] = field(default_factory=dict)


class LocalResourceProbe:
    """Capture client host and AIOS-bench process-tree resource usage."""

    def __init__(self, root_pid: int | None = None, *, drm_root: Path = Path("/sys/class/drm")) -> None:
        self.root_pid = int(root_pid or os.getpid())
        self.drm_root = drm_root
        self._cpu_state = _ProcessCpuState()
        psutil.cpu_percent(interval=None)

    def snapshot(self) -> ResourceSnapshot:
        captured_at = time.monotonic()
        processes = self._process_tree()
        rss_bytes = 0
        cpu_seconds: dict[tuple[int, float], float] = {}
        for process in processes:
            try:
                rss_bytes += int(process.memory_info().rss)
                times = process.cpu_times()
                cpu_seconds[(process.pid, process.create_time())] = float(times.user + times.system)
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                continue

        process_cpu_percent = self._process_cpu_percent(captured_at, cpu_seconds)
        virtual_memory = psutil.virtual_memory()
        gpu = self._linux_drm_gpu_snapshot()
        return ResourceSnapshot(
            captured_at=captured_at,
            process_rss_bytes=rss_bytes,
            process_cpu_percent=process_cpu_percent,
            process_count=len(cpu_seconds),
            host_cpu_percent=float(psutil.cpu_percent(interval=None)),
            host_ram_used_bytes=int(virtual_memory.used),
            gpu_busy_percent=gpu["gpu_busy_percent"],
            vram_used_bytes=gpu["vram_used_bytes"],
            vram_total_bytes=gpu["vram_total_bytes"],
            gpu_device_count=int(gpu["gpu_device_count"]),
        )

    def _process_tree(self) -> list[psutil.Process]:
        try:
            root = psutil.Process(self.root_pid)
            return [root, *root.children(recursive=True)]
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            return []

    def _process_cpu_percent(
        self,
        captured_at: float,
        current: dict[tuple[int, float], float],
    ) -> float:
        previous_at = self._cpu_state.captured_at
        previous = self._cpu_state.cpu_seconds
        self._cpu_state.captured_at = captured_at
        self._cpu_state.cpu_seconds = current
        if previous_at is None or captured_at <= previous_at:
            return 0.0
        elapsed = captured_at - previous_at
        cpu_delta = sum(
            max(0.0, seconds - previous[key])
            for key, seconds in current.items()
            if key in previous
        )
        return (cpu_delta / elapsed) * 100.0

    def _linux_drm_gpu_snapshot(self) -> dict[str, int | float | None]:
        if os.name != "posix" or not self.drm_root.is_dir():
            return self._empty_gpu_snapshot()

        devices: list[tuple[float | None, int | None, int | None]] = []
        for card in sorted(self.drm_root.glob("card[0-9]*")):
            device = card / "device"
            if not device.is_dir():
                continue
            busy = self._read_number(device / "gpu_busy_percent", float)
            used = self._read_number(device / "mem_info_vram_used", int)
            total = self._read_number(device / "mem_info_vram_total", int)
            if busy is None and used is None and total is None:
                continue
            devices.append((busy, used, total))

        if not devices:
            return self._empty_gpu_snapshot()
        busy_values = [value for value, _, _ in devices if value is not None]
        used_values = [value for _, value, _ in devices if value is not None]
        total_values = [value for _, _, value in devices if value is not None]
        return {
            "gpu_busy_percent": max(busy_values) if busy_values else None,
            "vram_used_bytes": sum(used_values) if used_values else None,
            "vram_total_bytes": sum(total_values) if total_values else None,
            "gpu_device_count": len(devices),
        }

    @staticmethod
    def _read_number(path: Path, converter: Callable[[str], int | float]) -> int | float | None:
        try:
            return converter(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    @staticmethod
    def _empty_gpu_snapshot() -> dict[str, int | float | None]:
        return {
            "gpu_busy_percent": None,
            "vram_used_bytes": None,
            "vram_total_bytes": None,
            "gpu_device_count": 0,
        }


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _series(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "p95": None, "peak": None}
    return {
        "mean": sum(values) / len(values),
        "p95": _p95(values),
        "peak": max(values),
    }


def summarize_snapshots(
    snapshots: list[ResourceSnapshot],
    *,
    poll_interval: float,
) -> dict[str, object]:
    if not snapshots:
        return {
            "available": False,
            "source": "local_process_tree",
            "error": "no resource samples captured",
        }

    baseline = snapshots[0]
    process_rss = [float(item.process_rss_bytes) for item in snapshots]
    process_cpu = [item.process_cpu_percent for item in snapshots]
    host_ram = [float(item.host_ram_used_bytes) for item in snapshots]
    host_cpu = [item.host_cpu_percent for item in snapshots]
    gpu_busy = [item.gpu_busy_percent for item in snapshots if item.gpu_busy_percent is not None]
    gpu_available = any(item.gpu_device_count > 0 for item in snapshots)
    vram_used = [float(item.vram_used_bytes) for item in snapshots if item.vram_used_bytes is not None]
    vram_totals = [int(item.vram_total_bytes) for item in snapshots if item.vram_total_bytes is not None]

    process_rss_summary = _series(process_rss)
    host_ram_summary = _series(host_ram)
    vram_summary = _series(vram_used)
    return {
        "available": True,
        "source": "local_process_tree",
        "scope": "aios_bench_process_tree_and_host",
        "sample_count": len(snapshots),
        "poll_interval_seconds": float(poll_interval),
        "process_tree": {
            "rss_baseline_bytes": baseline.process_rss_bytes,
            "rss_mean_bytes": process_rss_summary["mean"],
            "rss_p95_bytes": process_rss_summary["p95"],
            "rss_peak_bytes": process_rss_summary["peak"],
            "rss_peak_delta_bytes": max(
                0.0,
                float(process_rss_summary["peak"] or 0.0) - baseline.process_rss_bytes,
            ),
            "cpu_mean_percent": _series(process_cpu)["mean"],
            "cpu_p95_percent": _series(process_cpu)["p95"],
            "cpu_peak_percent": _series(process_cpu)["peak"],
            "process_count_peak": max(item.process_count for item in snapshots),
        },
        "host": {
            "ram_baseline_bytes": baseline.host_ram_used_bytes,
            "ram_mean_bytes": host_ram_summary["mean"],
            "ram_p95_bytes": host_ram_summary["p95"],
            "ram_peak_bytes": host_ram_summary["peak"],
            "ram_peak_delta_bytes": max(
                0.0,
                float(host_ram_summary["peak"] or 0.0) - baseline.host_ram_used_bytes,
            ),
            "cpu_mean_percent": _series(host_cpu)["mean"],
            "cpu_p95_percent": _series(host_cpu)["p95"],
            "cpu_peak_percent": _series(host_cpu)["peak"],
        },
        "gpu": {
            "available": gpu_available,
            "provider": "linux_drm_sysfs" if gpu_available else "unavailable",
            "scope": "host_total",
            "device_count": max(item.gpu_device_count for item in snapshots),
            "busy_mean_percent": _series([float(value) for value in gpu_busy])["mean"],
            "busy_p95_percent": _series([float(value) for value in gpu_busy])["p95"],
            "busy_peak_percent": _series([float(value) for value in gpu_busy])["peak"],
            "vram_baseline_bytes": baseline.vram_used_bytes,
            "vram_mean_bytes": vram_summary["mean"],
            "vram_p95_bytes": vram_summary["p95"],
            "vram_peak_bytes": vram_summary["peak"],
            "vram_peak_delta_bytes": (
                max(0.0, float(vram_summary["peak"] or 0.0) - baseline.vram_used_bytes)
                if baseline.vram_used_bytes is not None and vram_used
                else None
            ),
            "vram_total_bytes": max(vram_totals) if vram_totals else None,
        },
    }


class ResourceSampler:
    """Sample local resources off the benchmark execution path at bounded frequency."""

    def __init__(
        self,
        *,
        poll_interval: float = 1.0,
        snapshotter: Callable[[], ResourceSnapshot] | None = None,
    ) -> None:
        self.poll_interval = max(0.25, float(poll_interval))
        self._snapshotter = snapshotter or LocalResourceProbe().snapshot
        self._samples: list[ResourceSnapshot] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("resource sampler already started")
        self._capture()
        self._thread = threading.Thread(
            target=self._run,
            name="aios-bench-resource-sampler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> dict[str, object]:
        thread = self._thread
        if thread is None:
            return summarize_snapshots([], poll_interval=self.poll_interval)
        self._stop.set()
        thread.join(timeout=max(1.0, self.poll_interval * 2.0))
        self._capture()
        with self._lock:
            samples = list(self._samples)
        return summarize_snapshots(samples, poll_interval=self.poll_interval)

    def _run(self) -> None:
        while not self._stop.wait(self.poll_interval):
            self._capture()

    def _capture(self) -> None:
        try:
            snapshot = self._snapshotter()
        except Exception:
            return
        with self._lock:
            self._samples.append(snapshot)
