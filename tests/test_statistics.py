from aios_bench.statistics import aggregate_repeat_rows, wilson_interval


def _row(task, repeat, success, score):
    return {
        "harness": "piagent", "model": "ornith", "suite": "frontier_v3",
        "suite_revision": "rev", "execution_fingerprint": "fp", "task_id": task,
        "repeat": repeat, "orchestration_seed": 41 + repeat, "status": "completed",
        "comparable": True, "success": success, "score": score,
    }


def test_repeat_statistics_expose_variability():
    groups = aggregate_repeat_rows(
        [_row("autonomy_001", 1, True, 100), _row("autonomy_001", 2, False, 16),
         _row("autonomy_001", 3, False, 49)], suite="frontier_v3", suite_revision="rev",
    )
    group = groups[0]; task = group["tasks"]["autonomy_001"]
    assert group["repeat_count"] == 3
    assert group["score_range"] == [16.0, 100.0]
    assert task["pass_rate"] == 1 / 3
    assert task["pass_at_k"] is True
    assert task["pass_pow_k"] is False
    assert task["median_score"] == 49.0


def test_wilson_interval_is_bounded():
    low, high = wilson_interval(1, 3)
    assert 0 <= low < 1 / 3 < high <= 1
