from core.benchmark.models import Trajectory


def test_trajectory_persists_explicit_event_sequence_without_rewriting_adapter_metadata() -> None:
    trajectory = Trajectory(agent="piagent", task_id="task-1")
    events = [
        {
            "type": "tool_call",
            "timestamp": "2026-08-27T05:00:00.100000+00:00",
            "source": "adapter",
            "data": {"tool": "read", "call_id": "abc"},
        },
        {
            "type": "tool_result",
            "timestamp": "2026-08-27T05:00:00.100000+00:00",
            "source": "adapter",
            "data": {"tool": "read", "call_id": "abc", "is_error": False},
        },
    ]

    trajectory.apply_events(events)
    persisted = trajectory.to_dict()["events"]

    assert [event["sequence"] for event in persisted] == [1, 2]
    assert persisted[0]["timestamp"] == events[0]["timestamp"]
    assert persisted[0]["data"]["call_id"] == "abc"
    assert "sequence" not in events[0]  # caller-owned event objects are not mutated
    assert trajectory.telemetry_available is True


def test_trajectory_preserves_adapter_sequence_when_already_supplied() -> None:
    trajectory = Trajectory(agent="piagent", task_id="task-1")

    trajectory.apply_events([{"type": "assistant_message", "sequence": 42, "data": {}}])

    assert trajectory.events[0]["sequence"] == 42


def test_runner_owned_append_does_not_create_false_harness_telemetry_availability() -> None:
    trajectory = Trajectory(agent="piagent", task_id="task-1")

    trajectory.apply_events([])
    trajectory.append_event({"type": "server_metrics", "source": "runner", "data": {}})

    assert trajectory.telemetry_available is False
    assert trajectory.events[0]["sequence"] == 1
