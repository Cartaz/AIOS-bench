from core.benchmark.aios_index import AIOS_INDEX_CONTEXT_KIND
from core.benchmark.report import (
    canonical_capability_rows,
    latest_aios_index,
    selected_suite_revision,
    summarize_rows,
)


def _row(run_id: str, *, context=None, score: float = 100.0):
    return {
        "harness": "piagent",
        "model": "model",
        "suite": "frontier_v4",
        "suite_revision": "revision-a",
        "run_id": run_id,
        "task_id": "task",
        "category": "autonomy",
        "tier": 5,
        "status": "completed",
        "success": True,
        "score": score,
        "duration_seconds": 1.0,
        "experiment_context": context,
    }


def _manifest(run_id: str, *, context=None, finished="2026-08-31T12:00:00Z"):
    return {
        "harness": "piagent",
        "model": "model",
        "suite": "frontier_v4",
        "suite_revision": "revision-a",
        "run_id": run_id,
        "task_count": 1,
        "run_status": "completed",
        "started_at": "2026-08-31T11:00:00Z",
        "finished_at": finished,
        "experiment_context": context,
    }


def _key(run_id: str):
    return ("piagent", "model", "frontier_v4", "revision-a", run_id)


def test_aios_index_rows_are_not_canonical_capability_rows() -> None:
    context = {
        "kind": AIOS_INDEX_CONTEXT_KIND,
        "profile_id": "aios_index_v1",
        "profile_digest": "abc",
    }
    ordinary = _row("ordinary")
    compact = _row("compact", context=context)

    assert canonical_capability_rows([ordinary, compact]) == [ordinary]


def test_aios_index_run_is_separate_from_full_suite_leaderboard_eligibility() -> None:
    context = {
        "kind": AIOS_INDEX_CONTEXT_KIND,
        "profile_id": "aios_index_v1",
        "profile_digest": "digest-1",
    }
    rows = [_row("ordinary"), _row("compact", context=context)]
    manifests = {
        _key("ordinary"): _manifest("ordinary"),
        _key("compact"): _manifest("compact", context=context),
    }

    runs = summarize_rows(rows, manifests)
    ordinary = next(run for run in runs if run["run_id"] == "ordinary")
    compact = next(run for run in runs if run["run_id"] == "compact")

    assert ordinary["eligible"] is True
    assert compact["eligible"] is False
    assert compact["eligibility_reason"] == "aios_index_profile"
    assert compact["aios_index_profile_id"] == "aios_index_v1"
    assert compact["aios_index_profile_digest"] == "digest-1"
    assert selected_suite_revision(runs) == ("frontier_v4", "revision-a")


def test_latest_aios_index_is_selected_per_profile_harness_model() -> None:
    context = {
        "kind": AIOS_INDEX_CONTEXT_KIND,
        "profile_id": "aios_index_v1",
        "profile_digest": "digest-1",
    }
    rows = [_row("old", context=context), _row("new", context=context)]
    manifests = {
        _key("old"): _manifest("old", context=context, finished="2026-08-31T12:00:00Z"),
        _key("new"): _manifest("new", context=context, finished="2026-08-31T13:00:00Z"),
    }

    runs = summarize_rows(rows, manifests)
    latest = latest_aios_index(runs)

    assert len(latest) == 1
    assert latest[0]["run_id"] == "new"
