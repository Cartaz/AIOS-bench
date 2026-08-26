from aios_bench.resource_reporting import resource_efficiency_groups


def _resources(*, rss_base, rss_peak, cpu, vram_base=None, vram_peak=None, host_ram_delta=0):
    return {
        "available": True,
        "process_tree": {
            "rss_baseline_bytes": rss_base,
            "rss_peak_bytes": rss_peak,
            "rss_peak_delta_bytes": rss_peak - rss_base,
            "cpu_mean_percent": cpu,
            "vram_baseline_bytes": vram_base,
            "vram_peak_bytes": vram_peak,
            "vram_peak_delta_bytes": (
                vram_peak - vram_base
                if vram_base is not None and vram_peak is not None
                else None
            ),
            "gpu_engine_time_mean_percent": 12.5 if vram_peak is not None else None,
        },
        "host": {"ram_peak_delta_bytes": host_ram_delta},
        "gpu": {"vram_peak_delta_bytes": 100 if vram_peak is not None else None},
    }


def _row(task_id, *, client=None, server=None):
    return {
        "harness": "piagent",
        "model": "ornith",
        "suite": "frontier_v3",
        "suite_revision": "rev",
        "execution_fingerprint": "fp",
        "task_id": task_id,
        "status": "completed",
        "comparable": True,
        "client_resources": client,
        "server_resources": server,
    }


def test_resource_efficiency_keeps_client_and_server_separate():
    rows = [
        _row(
            "a",
            client=_resources(rss_base=100, rss_peak=200, cpu=20, vram_base=10, vram_peak=30),
            server=_resources(rss_base=1000, rss_peak=1400, cpu=50, vram_base=4000, vram_peak=4500),
        ),
        _row(
            "b",
            client=_resources(rss_base=120, rss_peak=320, cpu=40),
            server=_resources(rss_base=1100, rss_peak=1700, cpu=70, vram_base=4000, vram_peak=4800),
        ),
    ]

    group = resource_efficiency_groups(rows, suite="frontier_v3", suite_revision="rev")[0]

    assert group["client"]["measured_tasks"] == 2
    assert group["client"]["rss_peak_task_mean_bytes"] == 260
    assert group["client"]["rss_peak_max_bytes"] == 320
    assert group["client"]["vram_attributed_tasks"] == 1
    assert group["client"]["vram_peak_max_bytes"] == 30

    assert group["server"]["measured_tasks"] == 2
    assert group["server"]["rss_peak_task_mean_bytes"] == 1550
    assert group["server"]["rss_peak_delta_max_bytes"] == 600
    assert group["server"]["vram_baseline_task_mean_bytes"] == 4000
    assert group["server"]["vram_peak_max_bytes"] == 4800
    assert group["server"]["vram_peak_delta_task_mean_bytes"] == 650


def test_resource_efficiency_does_not_sum_memory_across_tasks():
    rows = [
        _row("a", client=_resources(rss_base=100, rss_peak=200, cpu=10)),
        _row("b", client=_resources(rss_base=100, rss_peak=300, cpu=10)),
    ]

    client = resource_efficiency_groups(rows)[0]["client"]

    assert client["rss_peak_task_mean_bytes"] == 250
    assert client["rss_peak_max_bytes"] == 300
    assert client["rss_peak_max_bytes"] != 500


def test_unavailable_and_noncomparable_rows_are_excluded():
    unavailable = {"available": False, "error": "no samples"}
    rows = [
        _row("good", client=_resources(rss_base=100, rss_peak=200, cpu=10)),
        _row("missing", client=unavailable),
        {**_row("noncomparable", client=_resources(rss_base=1, rss_peak=999, cpu=10)), "comparable": False},
    ]

    groups = resource_efficiency_groups(rows)

    assert len(groups) == 1
    assert groups[0]["client"]["measured_tasks"] == 1
    assert groups[0]["client"]["rss_peak_max_bytes"] == 200
    assert groups[0]["server"] is None
