from aios_bench.statistics import (
    aggregate_repeat_rows,
    failure_distributions,
    paired_comparisons,
    server_efficiency_groups,
    wilson_interval,
)


def _row(task, repeat, success, score):
    return {
        "harness": "piagent", "model": "ornith", "suite": "frontier_v3",
        "suite_revision": "rev", "execution_fingerprint": "fp", "task_id": task,
        "repeat": repeat, "orchestration_seed": 41 + repeat, "status": "completed",
        "comparable": True, "success": success, "score": score,
    }


def _paired_row(harness, task, repeat, score, success=True, fingerprint="model-fp"):
    return {
        "harness": harness,
        "model": "ornith",
        "suite": "frontier_v3",
        "suite_revision": "rev",
        "experiment_id": "exp-1",
        "schedule_mode": "matched_interleaved",
        "task_id": task,
        "task_seed": 1000 + repeat + len(task),
        "repeat": repeat,
        "status": "completed",
        "comparable": True,
        "success": success,
        "score": score,
        "model_identity_fingerprint": fingerprint,
        "model_strictly_comparable": True,
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


def test_paired_comparison_uses_only_matched_blocks():
    rows = [
        _paired_row("hermes", "task_a", 1, 80),
        _paired_row("piagent", "task_a", 1, 70),
        _paired_row("hermes", "task_b", 1, 40, success=False),
        _paired_row("piagent", "task_b", 1, 50),
        _paired_row("hermes", "task_a", 2, 90),
        _paired_row("piagent", "task_a", 2, 80),
        _paired_row("hermes", "unmatched", 1, 100),
    ]
    comparisons = paired_comparisons(rows, suite="frontier_v3", suite_revision="rev")
    assert len(comparisons) == 1
    comparison = comparisons[0]
    assert comparison["comparable"] is True
    assert comparison["matched_observations"] == 3
    assert comparison["matched_tasks"] == 2
    assert comparison["mean_score_delta_a_minus_b"] == 10 / 3
    assert comparison["wins_a"] == 2
    assert comparison["wins_b"] == 1
    assert comparison["ties"] == 0
    assert comparison["b_pass_a_fail"] == 1
    low, high = comparison["cluster_bootstrap_95"]
    assert low <= comparison["mean_score_delta_a_minus_b"] <= high
    assert 0 < comparison["sign_flip_p_value"] <= 1


def test_paired_comparison_rejects_model_identity_mismatch():
    rows = [
        _paired_row("hermes", "task_a", 1, 80, fingerprint="fp-a"),
        _paired_row("piagent", "task_a", 1, 70, fingerprint="fp-b"),
    ]
    comparison = paired_comparisons(rows)[0]
    assert comparison["comparable"] is False
    assert comparison["reason"] == "model_identity_mismatch"
    assert comparison["matched_observations"] == 0


def test_failure_distribution_counts_all_taxonomy_outcomes():
    rows = [
        {**_row("a", 1, True, 100), "failure_kind": "PASS"},
        {**_row("b", 1, False, 49), "failure_kind": "WRONG"},
        {**_row("c", 1, False, 0), "failure_kind": "TIMEOUT"},
    ]
    group = failure_distributions(rows, suite="frontier_v3", suite_revision="rev")[0]
    assert group["observations"] == 3
    assert group["counts"] == {"PASS": 1, "TIMEOUT": 1, "WRONG": 1}


def test_server_efficiency_uses_totals_not_mean_of_rates():
    base = {
        "harness": "piagent", "model": "ornith", "suite": "frontier_v3",
        "suite_revision": "rev", "execution_fingerprint": "fp",
        "usage_source": "server_verified",
    }
    rows = [
        {**base, "task_id": "a", "server_usage": {
            "trusted_for_efficiency": True, "prompt_tokens": 100, "output_tokens": 20,
            "prompt_seconds": 2.0, "generation_seconds": 1.0,
        }},
        {**base, "task_id": "b", "server_usage": {
            "trusted_for_efficiency": True, "prompt_tokens": 300, "output_tokens": 80,
            "prompt_seconds": 3.0, "generation_seconds": 4.0,
        }},
        {**base, "task_id": "ignored", "usage_source": "harness_reported", "server_usage": {
            "trusted_for_efficiency": False, "prompt_tokens": 999, "output_tokens": 999,
        }},
    ]
    group = server_efficiency_groups(rows, suite="frontier_v3", suite_revision="rev")[0]
    assert group["server_verified_tasks"] == 2
    assert group["prompt_tokens"] == 400
    assert group["output_tokens"] == 100
    assert group["prompt_tokens_per_second"] == 80
    assert group["generation_tokens_per_second"] == 20
