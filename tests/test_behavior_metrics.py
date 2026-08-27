from core.benchmark.behavior_metrics import behavior_efficiency_groups, task_behavior


def _event(kind: str, **data: object) -> dict[str, object]:
    return {"type": kind, "source": "test", "data": data}


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "agent": "piagent",
        "model": "model-a",
        "suite": "frontier-v4",
        "suite_revision": "rev-1",
        "execution_fingerprint": "fp-1",
        "status": "completed",
        "comparable": True,
        "duration_seconds": 120.0,
        "output_tokens": 600,
        "events": [
            _event("assistant_message", turn=True),
            _event("tool_call", tool="read", call_id="1"),
            _event("tool_result", tool="read", call_id="1", is_error=False),
            _event("tool_call", tool="read", call_id="2"),
            _event("tool_result", tool="read", call_id="2", is_error=True),
            _event("tool_call", tool="edit", call_id="3"),
            _event("retry"),
            _event("file_read"),
            _event("file_write"),
        ],
    }
    row.update(overrides)
    return row


def test_task_behavior_uses_only_canonical_non_inferred_events() -> None:
    row = _row()
    row["events"] = [*row["events"], _event("tool_call", tool="bash", inferred=True)]
    behavior = task_behavior(row)
    assert behavior["tool_calls"] == 3
    assert behavior["unique_tools"] == 2
    assert behavior["consecutive_repeated_tool_calls"] == 1
    assert behavior["tool_errors"] == 1
    assert behavior["assistant_turns"] == 1
    assert behavior["retries"] == 1
    assert behavior["scope"] == "canonical_non_inferred_events"
    assert behavior["affects_score"] is False


def test_behavior_groups_keep_execution_profiles_separate() -> None:
    rows = [_row(), _row(duration_seconds=60.0), _row(agent="claude", execution_fingerprint="fp-2")]
    groups = behavior_efficiency_groups(rows, suite="frontier-v4", suite_revision="rev-1")
    assert len(groups) == 2
    pi = next(group for group in groups if group["harness"] == "piagent")
    assert pi["tasks_with_behavior_telemetry"] == 2
    assert pi["mean_tool_calls"] == 3.0
    assert pi["total_tool_errors"] == 2
    assert pi["affects_score"] is False


def test_behavior_groups_use_persisted_behavior_when_available() -> None:
    row = _row(events=[])
    row["agent_behavior"] = {
        "telemetry_available": True,
        "assistant_turns": 2,
        "tool_calls": 4,
        "unique_tools": 3,
        "consecutive_repeated_tool_calls": 0,
        "tool_errors": 0,
        "retries": 0,
        "file_reads": 2,
        "file_writes": 1,
        "subagent_starts": 0,
        "refusals": 0,
        "duration_seconds": 30.0,
        "output_tokens": 120,
        "tool_calls_per_minute": 8.0,
        "output_tokens_per_tool_call": 30.0,
    }
    groups = behavior_efficiency_groups([row])
    assert len(groups) == 1
    assert groups[0]["mean_assistant_turns"] == 2.0
    assert groups[0]["mean_tool_calls"] == 4.0


def test_behavior_groups_exclude_noncomparable_and_unavailable_rows() -> None:
    rows = [_row(), _row(comparable=False), _row(events=[]), _row(status="unsupported")]
    groups = behavior_efficiency_groups(rows)
    assert len(groups) == 1
    assert groups[0]["tasks_with_behavior_telemetry"] == 1
