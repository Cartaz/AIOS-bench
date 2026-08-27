from core.benchmark.reference_trajectory_reporting import reference_trajectory_groups


def _row(*, complete: bool, milestone: float, events: int | None, effort: float | None, post: int | None) -> dict:
    return {
        "harness": "piagent",
        "model": "test-model",
        "suite": "frontier_v4",
        "suite_revision": "test-revision",
        "execution_fingerprint": "fingerprint",
        "status": "completed",
        "comparable": True,
        "reference_trajectory": {
            "available": True,
            "complete": complete,
            "milestone_completion": milestone,
            "events_to_completion": events,
            "reference_events_to_completion": 5,
            "effort_multiple_of_reference": effort,
            "post_completion_events": post,
            "affects_score": False,
        },
    }


def test_reference_trajectory_groups_aggregate_persisted_metrics_only() -> None:
    groups = reference_trajectory_groups(
        [
            _row(complete=True, milestone=1.0, events=5, effort=1.0, post=2),
            _row(complete=False, milestone=2 / 3, events=None, effort=None, post=None),
        ],
        suite="frontier_v4",
        suite_revision="test-revision",
    )

    assert len(groups) == 1
    group = groups[0]
    assert group["tasks_with_reference_trajectory"] == 2
    assert group["complete_reference_trajectories"] == 1
    assert group["reference_trajectory_completion_rate"] == 0.5
    assert group["mean_milestone_completion"] == (1.0 + 2 / 3) / 2
    assert group["mean_events_to_completion"] == 5.0
    assert group["mean_reference_events_to_completion"] == 5.0
    assert group["mean_effort_multiple_of_reference"] == 1.0
    assert group["mean_post_completion_events"] == 2.0
    assert group["affects_score"] is False


def test_unavailable_noncomparable_and_other_suite_rows_are_excluded() -> None:
    unavailable = _row(complete=True, milestone=1.0, events=5, effort=1.0, post=0)
    unavailable["reference_trajectory"] = {"available": False, "reason": "required_telemetry_missing"}
    noncomparable = _row(complete=True, milestone=1.0, events=5, effort=1.0, post=0)
    noncomparable["comparable"] = False
    other_suite = _row(complete=True, milestone=1.0, events=5, effort=1.0, post=0)
    other_suite["suite"] = "frontier_v3"

    assert reference_trajectory_groups(
        [unavailable, noncomparable, other_suite],
        suite="frontier_v4",
        suite_revision="test-revision",
    ) == []
