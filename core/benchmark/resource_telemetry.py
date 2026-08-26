from __future__ import annotations

import math
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import psutil

from .linux_drm import read_host_drm_usage, read_process_drm_usage


@dataclass(frozen=True)
class ResourceSnapshot:
    captured_at: float
    process_rss_bytes: int
    process_cpu_percent: float
    process_count: int
    host_cpu_percent: float
    host_ram_used_bytes: int
    process_gpu_engine_time_percent: float | None = None
    process_vram_used_bytes: int | None = None
    process_gpu_client_count: int = 0
    gpu_busy_percent: float | None = None
    vram_used_bytes: int | None = None
    vram_total_bytes: int | None = None
    gpu_device_count: int = 0


@dataclass
class _ProcessCpuState:
    captured_at: float | None = None
    cpu_seconds: dict[tuple[int, float], float] = field(default_factory=dict)


@dataclass
class _ProcessGpuState:
    captured_at: float | None = None
    engine_ns: dict[str, int] = field(default_factory=dict)


class LocalResourceProbe:
    """Capture client host and AIOS-bench process-tree resource usage."""

    def __init__(
        self,
        root_pid: int | None = None,
        *,
        drm_root: Path = Path("/sys/class/drm"),
        proc_root: Path = Path("/proc"),
    ) -> None:
        self.root_pid = int(root_pid or os.getpid())
        self.drm_root = drm_root
        self.proc_root = proc_root
        self._cpu_state = _ProcessCpuState()
        self._gpu_state = _ProcessGpuState()
        psutil.cpu_percent(interval=None)

    def snapshot(self) -> ResourceSnapshot:
        captured_at = time.monotonic()
        processes = self._process_tree()
        rss_bytes = 0
        cpu_seconds: dict[tuple[int, float], float] = {}
        pids: list[int] = []
        for process in processes:
            try:
                rss_bytes += int(process.memory_info().rss)
                times = process.cpu_times()
                cpu_seconds[(process.pid, process.create_time())] = float(times.user + times.system)
                pids.append(process.pid)
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                continue

        process_cpu_percent = self._process_cpu_percent(captured_at, cpu_seconds)
        process_gpu = read_process_drm_usage(pids, proc_root=self.proc_root)
        process_gpu_percent = self._process_gpu_percent(
            captured_at,
            process_gpu.engine_ns,
            available=process_gpu.available,
        )
        virtual_memory = psutil.virtual_memory()
        host_gpu = read_host_drm_usage(self.drm_root)
        return ResourceSnapshot(
            captured_at=captured_at,
            process_rss_bytes=rss_bytes,
            process_cpu_percent=process_cpu_percent,
            process_count=len(cpu_seconds),
            host_cpu_percent=float(psutil.cpu_percent(interval=None)),
            host_ram_used_bytes=int(virtual_memory.used),
            process_gpu_engine_time_percent=process_gpu_percent,
            process_vram_used_bytes=process_gpu.vram_used_bytes,
            process_gpu_client_count=process_gpu.client_count,
            gpu_busy_percent=host_gpu.gpu_busy_percent,
            vram_used_bytes=host_gpu.vram_used_bytes,
            vram_total_bytes=host_gpu.vram_total_bytes,
            gpu_device_count=host_gpu.device_count,
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

    def _process_gpu_percent(
        self,
        captured_at: float,
        current: dict[str, int],
        *,
        available: bool,
    ) -> float | None:
        previous_at = self._gpu_state.captured_at
        previous = self._gpu_state.engine_ns
        if not available:
            self._gpu_state = _ProcessGpuState(captured_at, {})
            return None

        retained: dict[str, int] = {}
        busy_delta_ns = 0
        for key, value in current.items():
            prior = previous.get(key)
            if prior is None:
                retained[key] = value
            elif value < prior:
                # DRM counters may temporarily appear non-monotonic. Kernel
                # guidance says to retain the larger value until they catch up.
                retained[key] = prior
            else:
                retained[key] = value
                busy_delta_ns += value - prior
        self._gpu_state = _ProcessGpuState(captured_at, retained)
        if previous_at is None or captured_at <= previous_at:
            return 0.0
        elapsed_ns = (captured_at - previous_at) * 1_000_000_000.0
        return (busy_delta_ns / elapsed_ns) * 100.0


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
    process_gpu = [
        item.process_gpu_engine_time_percent
        for item in snapshots
        if item.process_gpu_engine_time_percent is not None
    ]
    process_vram = [
        float(item.process_vram_used_bytes)
        for item in snapshots
        if item.process_vram_used_bytes is not None
    ]
    host_ram = [float(item.host_ram_used_bytes) for item in snapshots]
    host_cpu = [item.host_cpu_percent for item in snapshots]
    gpu_busy = [item.gpu_busy_percent for item in snapshots if item.gpu_busy_percent is not None]
    host_gpu_available = any(item.gpu_device_count > 0 for item in snapshots)
    vram_used = [float(item.vram_used_bytes) for item in snapshots if item.vram_used_bytes is not None]
    vram_totals = [int(item.vram_total_bytes) for item in snapshots if item.vram_total_bytes is not None]

    process_rss_summary = _series(process_rss)
    process_gpu_summary = _series([float(value) for value in process_gpu])
    process_vram_summary = _series(process_vram)
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
            "gpu_attribution_available": bool(process_gpu or process_vram),
            "gpu_provider": "linux_drm_fdinfo" if process_gpu or process_vram else "unavailable",
            "gpu_scope": "drm_client_attributed",
            "gpu_engine_time_mean_percent": process_gpu_summary["mean"],
            "gpu_engine_time_p95_percent": process_gpu_summary["p95"],
            "gpu_engine_time_peak_percent": process_gpu_summary["peak"],
            "gpu_engine_time_semantics": "summed_drm_engine_busy_time",
            "vram_mean_bytes": process_vram_summary["mean"],
            "vram_p95_bytes": process_vram_summary["p95"],
            "vram_peak_bytes": process_vram_summary["peak"],
            "gpu_client_count_peak": max(item.process_gpu_client_count for item in snapshots),
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
            "available": host_gpu_available,
            "provider": "linux_drm_sysfs" if host_gpu_available else "unavailable",
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
        self._summary: dict[str, object] | None = None

    def start(self) -> None:
        if self._thread is not None or self._summary is not None:
            raise RuntimeError("resource sampler already started")
        self._capture()
        thread = threading.Thread(
            target=self._run,
            name="aios-bench-resource-sampler",
            daemon=True,
        )
        thread.start()
        self._thread = thread

    def stop(self) -> dict[str, object]:
        if self._summary is not None:
            return self._summary
        thread = self._thread
        if thread is None:
            self._summary = summarize_snapshots([], poll_interval=self.poll_interval)
            return self._summary
        self._stop.set()
        thread.join(timeout=max(1.0, self.poll_interval * 2.0))
        self._capture()
        with self._lock:
            samples = list(self._samples)
        self._summary = summarize_snapshots(samples, poll_interval=self.poll_interval)
        return self._summary

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
