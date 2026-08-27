from core.benchmark.coverage_reporting import (
    coverage_completeness_groups,
    task_coverage_metrics,
)


def _row(*, tp: int, fp: int, fn: int, completion: float) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {
        "harness": "piagent",
        "model": "test-model",
        "suite": "frontier_v4",
        "suite_revision": "test-revision",
        "execution_fingerprint": "fingerprint",
        "status": "completed",
        "comparable": True,
        "evaluation": {
            "results": [{
                "metrics": {
                    "schema": "aios-bench/coverage/v1",
                    "true_positives": tp,
                    "false_positives": fp,
                    "false_negatives": fn,
                    "precision": precision,
                    "recall": recall,
                    "completion": completion,
                    "required_count": tp + fn,
                }
            }]
        },
    }


def test_task_coverage_reads_only_persisted_coverage_schema() -> None:
    row = _row(tp=3, fp=0, fn=1, completion=0.75)

    metrics = task_coverage_metrics(row)

    assert metrics is not None
    assert metrics["true_positives"] == 3
    assert metrics["completion"] == 0.75


def test_coverage_groups_aggregate_without_affecting_score() -> None:
    groups = coverage_completeness_groups([
        _row(tp=4, fp=0, fn=0, completion=1.0),
        _row(tp=3, fp=1, fn=1, completion=0.6),
    ], suite="frontier_v4", suite_revision="test-revision")

    assert len(groups) == 1
    group = groups[0]
    assert group["tasks_with_coverage"] == 2
    assert group["exact_completion_tasks"] == 1
    assert group["total_true_positives"] == 7
    assert group["total_false_positives"] == 1
    assert group["total_false_negatives"] == 1
    assert group["mean_completion"] == 0.8
    assert group["affects_score"] is False


def test_noncomparable_and_other_suite_rows_are_excluded() -> None:
    excluded = _row(tp=4, fp=0, fn=0, completion=1.0)
    excluded["comparable"] = False
    other_suite = _row(tp=4, fp=0, fn=0, completion=1.0)
    other_suite["suite"] = "frontier_v3"

    groups = coverage_completeness_groups(
        [excluded, other_suite],
        suite="frontier_v4",
        suite_revision="test-revision",
    )

    assert groups == []
