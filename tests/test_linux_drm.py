from __future__ import annotations

from core.benchmark.linux_drm import (
    parse_drm_fdinfo,
    read_host_drm_usage,
    read_process_drm_usage,
)


FDINFO = """
pos: 0
flags: 02400002
drm-driver: amdgpu
drm-pdev: 0000:03:00.0
drm-client-id: 17
drm-engine-gfx: 1500000000 ns
drm-engine-compute: 250000000 ns
drm-memory-vram: 4 MiB
drm-memory-gtt: 8 MiB
"""


def test_parse_fdinfo_uses_vram_only_and_keeps_engine_counters():
    usage = parse_drm_fdinfo(FDINFO)
    assert usage is not None
    assert usage.client_key == "amdgpu|0000:03:00.0|17"
    assert usage.vram_used_bytes == 4 * 1024**2
    assert usage.engine_ns == {"gfx": 1_500_000_000, "compute": 250_000_000}


def test_fdinfo_without_client_id_fails_closed():
    assert parse_drm_fdinfo("drm-driver: amdgpu\ndrm-memory-vram: 4 MiB\n") is None


def test_process_usage_deduplicates_shared_drm_client(tmp_path):
    fdinfo = tmp_path / "41" / "fdinfo"
    fdinfo.mkdir(parents=True)
    (fdinfo / "3").write_text(FDINFO, encoding="utf-8")
    (fdinfo / "4").write_text(FDINFO, encoding="utf-8")

    usage = read_process_drm_usage([41], proc_root=tmp_path)

    assert usage.available is True
    assert usage.client_count == 1
    assert usage.vram_used_bytes == 4 * 1024**2
    assert usage.engine_ns == {
        "amdgpu|0000:03:00.0|17|gfx": 1_500_000_000,
        "amdgpu|0000:03:00.0|17|compute": 250_000_000,
    }


def test_host_drm_reads_amd_sysfs_counters(tmp_path):
    device = tmp_path / "card0" / "device"
    device.mkdir(parents=True)
    (device / "gpu_busy_percent").write_text("73\n", encoding="utf-8")
    (device / "mem_info_vram_used").write_text("4096\n", encoding="utf-8")
    (device / "mem_info_vram_total").write_text("8192\n", encoding="utf-8")

    usage = read_host_drm_usage(tmp_path)

    assert usage.available is True
    assert usage.gpu_busy_percent == 73.0
    assert usage.vram_used_bytes == 4096
    assert usage.vram_total_bytes == 8192
    assert usage.device_count == 1
