from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class HostDrmUsage:
    available: bool
    gpu_busy_percent: float | None = None
    vram_used_bytes: int | None = None
    vram_total_bytes: int | None = None
    device_count: int = 0


@dataclass(frozen=True)
class ProcessDrmUsage:
    available: bool
    vram_used_bytes: int | None = None
    engine_ns: dict[str, int] = field(default_factory=dict)
    client_count: int = 0


@dataclass(frozen=True)
class DrmClientUsage:
    client_key: str
    vram_used_bytes: int | None
    engine_ns: dict[str, int]


def _read_number(path: Path, converter):
    try:
        return converter(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def read_host_drm_usage(drm_root: Path = Path("/sys/class/drm")) -> HostDrmUsage:
    """Read host-total GPU busy and VRAM counters exposed by DRM sysfs."""
    if os.name != "posix" or not drm_root.is_dir():
        return HostDrmUsage(False)

    devices: list[tuple[float | None, int | None, int | None]] = []
    for card in sorted(drm_root.glob("card[0-9]*")):
        device = card / "device"
        if not device.is_dir():
            continue
        busy = _read_number(device / "gpu_busy_percent", float)
        used = _read_number(device / "mem_info_vram_used", int)
        total = _read_number(device / "mem_info_vram_total", int)
        if busy is None and used is None and total is None:
            continue
        devices.append((busy, used, total))

    if not devices:
        return HostDrmUsage(False)
    busy_values = [value for value, _, _ in devices if value is not None]
    used_values = [value for _, value, _ in devices if value is not None]
    total_values = [value for _, _, value in devices if value is not None]
    return HostDrmUsage(
        True,
        gpu_busy_percent=max(busy_values) if busy_values else None,
        vram_used_bytes=sum(used_values) if used_values else None,
        vram_total_bytes=sum(total_values) if total_values else None,
        device_count=len(devices),
    )


def _parse_bytes(value: str) -> int | None:
    parts = value.strip().split()
    if not parts:
        return None
    try:
        amount = int(parts[0])
    except ValueError:
        return None
    unit = parts[1].lower() if len(parts) > 1 else "b"
    multiplier = {
        "b": 1,
        "bytes": 1,
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
    }.get(unit)
    return amount * multiplier if multiplier is not None else None


def _parse_counter_ns(value: str) -> int | None:
    parts = value.strip().split()
    if not parts:
        return None
    try:
        amount = int(parts[0])
    except ValueError:
        return None
    if len(parts) == 1 or parts[1].lower() == "ns":
        return amount
    return None


def parse_drm_fdinfo(text: str) -> DrmClientUsage | None:
    """Parse the standardized DRM client usage subset needed by AIOS-bench."""
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        if key.startswith("drm-"):
            fields[key] = value.strip()

    driver = fields.get("drm-driver")
    client_id = fields.get("drm-client-id")
    if not driver or not client_id:
        # Without the standardized client id duplicated/shared descriptors cannot
        # be de-duplicated reliably, so attribution fails closed.
        return None
    device = fields.get("drm-pdev", "device-unknown")
    client_key = f"{driver}|{device}|{client_id}"

    resident_vram: list[int] = []
    legacy_vram: list[int] = []
    engine_ns: dict[str, int] = {}
    for key, value in fields.items():
        if key.startswith("drm-resident-") and "vram" in key.removeprefix("drm-resident-").lower():
            parsed = _parse_bytes(value)
            if parsed is not None:
                resident_vram.append(parsed)
        elif key.startswith("drm-memory-") and "vram" in key.removeprefix("drm-memory-").lower():
            parsed = _parse_bytes(value)
            if parsed is not None:
                legacy_vram.append(parsed)
        elif key.startswith("drm-engine-") and not key.startswith("drm-engine-capacity-"):
            parsed = _parse_counter_ns(value)
            if parsed is not None:
                engine_ns[key.removeprefix("drm-engine-")] = parsed

    vram_values = resident_vram if resident_vram else legacy_vram
    return DrmClientUsage(
        client_key=client_key,
        vram_used_bytes=sum(vram_values) if vram_values else None,
        engine_ns=engine_ns,
    )


def read_process_drm_usage(
    pids: list[int],
    *,
    proc_root: Path = Path("/proc"),
) -> ProcessDrmUsage:
    """Aggregate DRM usage for a process tree without double-counting clients."""
    if os.name != "posix" or not proc_root.is_dir():
        return ProcessDrmUsage(False)

    clients: dict[str, DrmClientUsage] = {}
    for pid in pids:
        fdinfo_dir = proc_root / str(pid) / "fdinfo"
        try:
            entries = list(fdinfo_dir.iterdir())
        except OSError:
            continue
        for path in entries:
            try:
                usage = parse_drm_fdinfo(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if usage is not None:
                clients.setdefault(usage.client_key, usage)

    if not clients:
        return ProcessDrmUsage(False)

    vram_values = [usage.vram_used_bytes for usage in clients.values() if usage.vram_used_bytes is not None]
    engine_ns: dict[str, int] = {}
    for usage in clients.values():
        for engine, value in usage.engine_ns.items():
            engine_ns[f"{usage.client_key}|{engine}"] = value
    return ProcessDrmUsage(
        True,
        vram_used_bytes=sum(vram_values) if vram_values else None,
        engine_ns=engine_ns,
        client_count=len(clients),
    )
