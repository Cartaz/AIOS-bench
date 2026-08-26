from __future__ import annotations

import json
from pathlib import Path

from aios_bench.dashboard import build_dashboard
from aios_bench.statistics import augment_summary_file


def _resources(*, rss_base: int, rss_peak: int, vram_base: int, vram_peak: int) -> dict:
    return {
        "available": True,
        "process_tree": {
            "rss_baseline_bytes": rss_base,
            "rss_peak_bytes": rss_peak,
            "rss_peak_delta_bytes": rss_peak - rss_base,
            "cpu_mean_percent": 25.0,
            "vram_baseline_bytes": vram_base,
            "vram_peak_bytes": vram_peak,
            "vram_peak_delta_bytes": vram_peak - vram_base,
            "gpu_engine_time_mean_percent": 10.0,
        },
        "host": {"ram_peak_delta_bytes": 1234},
        "gpu": {"vram_peak_delta_bytes": 5678},
    }


def _write_run(root: Path) -> None:
    run_dir = root / "piagent" / "ornith" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    metadata = {
        "harness": "piagent",
        "model": "ornith",
        "run_id": "run-1",
        "suite": "frontier_v3",
        "suite_revision": "rev",
        "execution_fingerprint": "fp",
        "status": "completed",
        "task_count": 1,
        "started_at": "2026-08-26T10:00:00Z",
        "finished_at": "2026-08-26T10:01:00Z",
    }
    row = {
        "task_id": "task_a",
        "task_revision": 1,
        "status": "completed",
        "comparable": True,
        "success": True,
        "score": 100,
        "category": "coding",
        "tier": 3,
        "client_resources": _resources(
            rss_base=100 * 1024**2,
            rss_peak=300 * 1024**2,
            vram_base=64 * 1024**2,
            vram_peak=128 * 1024**2,
        ),
        "server_resources": _resources(
            rss_base=8 * 1024**3,
            rss_peak=9 * 1024**3,
            vram_base=4 * 1024**3,
            vram_peak=5 * 1024**3,
        ),
    }
    (run_dir / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_summary_contains_resource_efficiency_without_changing_score(tmp_path: Path) -> None:
    _write_run(tmp_path)
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps({"selected_suite": "frontier_v3", "selected_suite_revision": "rev"}),
        encoding="utf-8",
    )

    augment_summary_file(summary_path, tmp_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    group = summary["resource_efficiency"][0]
    assert group["harness"] == "piagent"
    assert group["client"]["rss_peak_max_bytes"] == 300 * 1024**2
    assert group["server"]["vram_baseline_task_mean_bytes"] == 4 * 1024**3
    assert group["server"]["vram_peak_delta_task_mean_bytes"] == 1 * 1024**3
    assert "score" not in group


def test_dashboard_renders_separate_client_and_server_resource_panels(tmp_path: Path) -> None:
    _write_run(tmp_path)

    dashboard = build_dashboard(tmp_path).read_text(encoding="utf-8")

    assert "Client resource cost" in dashboard
    assert "Inference server / model resource cost" in dashboard
    assert "300.0 MiB" in dashboard
    assert "4.00 GiB" in dashboard
    assert "5.00 GiB" in dashboard
    assert "VRAM baseline" in dashboard
