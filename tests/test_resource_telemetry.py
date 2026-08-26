from __future__ import annotations

from core.benchmark.resource_telemetry import (
    LocalResourceProbe,
    ResourceSampler,
    ResourceSnapshot,
    summarize_snapshots,
)


def _snapshot(
    captured_at: float,
    *,
    rss: int,
    proc_cpu: float,
    count: int,
    host_cpu: float,
    host_ram: int,
    gpu: float | None = None,
    vram: int | None = None,
    vram_total: int | None = None,
) -> ResourceSnapshot:
    return ResourceSnapshot(
        captured_at=captured_at,
        process_rss_bytes=rss,
        process_cpu_percent=proc_cpu,
        process_count=count,
        host_cpu_percent=host_cpu,
        host_ram_used_bytes=host_ram,
        gpu_busy_percent=gpu,
        vram_used_bytes=vram,
        vram_total_bytes=vram_total,
        gpu_device_count=1 if gpu is not None or vram is not None else 0,
    )


def test_summary_keeps_process_tree_and_host_cost_separate():
    summary = summarize_snapshots(
        [
            _snapshot(
                1.0,
                rss=100,
                proc_cpu=0,
                count=1,
                host_cpu=10,
                host_ram=1000,
                gpu=5,
                vram=200,
                vram_total=1000,
            ),
            _snapshot(
                2.0,
                rss=250,
                proc_cpu=80,
                count=3,
                host_cpu=50,
                host_ram=1400,
                gpu=60,
                vram=500,
                vram_total=1000,
            ),
        ],
        poll_interval=1.0,
    )
    assert summary["available"] is True
    assert summary["process_tree"]["rss_peak_bytes"] == 250
    assert summary["process_tree"]["rss_peak_delta_bytes"] == 150
    assert summary["process_tree"]["process_count_peak"] == 3
    assert summary["host"]["ram_peak_delta_bytes"] == 400
    assert summary["gpu"]["scope"] == "host_total"
    assert summary["gpu"]["vram_peak_delta_bytes"] == 300


def test_sampler_captures_baseline_and_final_sample():
    values = iter([
        _snapshot(1.0, rss=100, proc_cpu=0, count=1, host_cpu=10, host_ram=1000),
        _snapshot(2.0, rss=150, proc_cpu=20, count=2, host_cpu=30, host_ram=1100),
    ])
    sampler = ResourceSampler(poll_interval=10.0, snapshotter=lambda: next(values))
    sampler.start()
    summary = sampler.stop()
    assert summary["sample_count"] == 2
    assert summary["process_tree"]["rss_peak_bytes"] == 150


def test_empty_summary_fails_open_without_inventing_zero_usage():
    summary = summarize_snapshots([], poll_interval=1.0)
    assert summary["available"] is False
    assert "error" in summary


def test_linux_drm_probe_reads_amd_busy_and_vram(tmp_path):
    device = tmp_path / "card0" / "device"
    device.mkdir(parents=True)
    (device / "gpu_busy_percent").write_text("73\n", encoding="utf-8")
    (device / "mem_info_vram_used").write_text("4096\n", encoding="utf-8")
    (device / "mem_info_vram_total").write_text("8192\n", encoding="utf-8")

    probe = LocalResourceProbe(drm_root=tmp_path)
    gpu = probe._linux_drm_gpu_snapshot()

    assert gpu == {
        "gpu_busy_percent": 73.0,
        "vram_used_bytes": 4096,
        "vram_total_bytes": 8192,
        "gpu_device_count": 1,
    }
