from core.benchmark.aios_index import AIOSIndexProfile, IndexEntry, get_aios_index_profile
from core.benchmark.frontier_runner import semantic_source_paths
from core.benchmark.paths import REPO_ROOT
from core.benchmark.report import latest_aios_index


def test_v49_orchestration_modules_do_not_change_suite_semantic_revision() -> None:
    names = {path.name for path in semantic_source_paths(REPO_ROOT)}

    assert "aios_index.py" not in names
    assert "aios_index_execution.py" not in names
    assert "health.py" not in names


def test_aios_index_comparison_identity_changes_with_profile_definition() -> None:
    profile = get_aios_index_profile()
    changed = AIOSIndexProfile(
        profile.id,
        profile.entries[:-1]
        + (IndexEntry("tool_recovery_001", "alternate_role", "tool_recovery"),),
    )

    assert changed.id == profile.id
    assert changed.digest != profile.digest
    assert changed.comparison_id != profile.comparison_id


def test_reporting_cannot_merge_distinct_profile_revisions_by_stable_name() -> None:
    profile = get_aios_index_profile()
    changed = AIOSIndexProfile(
        profile.id,
        profile.entries[:-1]
        + (IndexEntry("tool_recovery_001", "alternate_role", "tool_recovery"),),
    )
    base = {
        "eligibility_reason": "aios_index_profile",
        "complete": True,
        "harness": "piagent",
        "model": "model",
        "suite": "frontier_v4",
        "suite_revision": "revision",
        "started_at": "2026-09-01T10:00:00Z",
        "finished_at": "2026-09-01T10:10:00Z",
    }
    runs = [
        {
            **base,
            "run_id": "original",
            "aios_index_profile_id": profile.comparison_id,
            "aios_index_profile_digest": profile.digest,
        },
        {
            **base,
            "run_id": "changed",
            "aios_index_profile_id": changed.comparison_id,
            "aios_index_profile_digest": changed.digest,
        },
    ]

    latest = latest_aios_index(runs)

    assert {run["run_id"] for run in latest} == {"original", "changed"}
    assert len({run["aios_index_profile_id"] for run in latest}) == 2
