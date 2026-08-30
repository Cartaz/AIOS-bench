from __future__ import annotations

from pathlib import Path

from aios_bench.ablations import skill_ablation_pairs
from aios_bench.frontier_v4_runner import FrontierV4Runner
from aios_bench.interventions import ExecutionCondition, skill_for_task, skill_task_ids
from aios_bench.runner import AGENTS
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"


def _row(
    mode: str,
    *,
    score: float,
    success: bool,
    repeat: int = 1,
    digest: str = "same-variant",
    model_fp: str = "model-fp",
    ablation_fp: str = "ablation-fp",
    skill_digest: str = "skill-digest",
) -> dict:
    return {
        "harness": "piagent",
        "agent": "piagent",
        "model": "ornith",
        "suite": "frontier_v4",
        "suite_revision": "revision-v43",
        "task_id": "tool_recovery_001",
        "variant_family": "tool_recovery",
        "variant_parameters": {
            "case_count": 24,
            "required_actions": 5,
            "distractor_tools": 4,
            "transient_failures": 3,
            "incomplete_responses": 8,
        },
        "variant_digest": digest,
        "experiment_id": "exp-ablation",
        "schedule_mode": "matched_interleaved",
        "repeat": repeat,
        "task_seed": 1234 + repeat,
        "model_identity_fingerprint": model_fp,
        "model_strictly_comparable": True,
        "ablation_execution_fingerprint": ablation_fp,
        "execution_fingerprint": f"profile-{mode}",
        "skill_mode": mode,
        "skill_available": True,
        "skill_applied": mode == "curated_skill",
        "skill_id": "tool-recovery/v1",
        "skill_digest": skill_digest,
        "status": "completed" if success else "failed",
        "comparable": True,
        "success": success,
        "score": score,
        "input_tokens": 100 if mode == "no_skill" else 140,
        "output_tokens": 50 if mode == "no_skill" else 45,
    }


def test_skill_catalog_targets_only_owned_v4_tasks() -> None:
    tasks = {task.id: task for task in load_tasks(TASK_ROOT, "frontier_v4")}

    assert skill_task_ids() == frozenset({"tool_use_lineage_001", "tool_recovery_001"})
    for task_id in skill_task_ids():
        package = skill_for_task(tasks[task_id])
        assert package is not None
        assert package.digest
        assert task_id in package.task_ids


def test_curated_condition_changes_prompt_without_variant_specific_answers() -> None:
    task = next(
        task
        for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "tool_recovery_001"
    )
    base = "BASE PROMPT"
    no_skill = ExecutionCondition("no_skill").augment_prompt(task, base)
    curated = ExecutionCondition("curated_skill").augment_prompt(task, base)

    assert no_skill == base
    assert curated.startswith(base)
    assert "CURATED PROCEDURAL SKILL" in curated
    assert "idempotency key" in curated
    assert "CASE-" not in curated


def test_runner_execution_identity_separates_arms_but_pairs_ablation_profile(tmp_path: Path) -> None:
    task = next(
        task
        for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "tool_recovery_001"
    )
    no_skill = FrontierV4Runner(
        ROOT,
        AGENTS["piagent"],
        tmp_path / "no",
        task_timeout=1,
        total_timeout=None,
        model="test",
        run_id="no-skill",
        skill_mode="no_skill",
    )
    curated = FrontierV4Runner(
        ROOT,
        AGENTS["piagent"],
        tmp_path / "curated",
        task_timeout=1,
        total_timeout=None,
        model="test",
        run_id="curated",
        skill_mode="curated_skill",
    )

    no_skill._workspace(task)
    curated._workspace(task)
    no_identity = no_skill._result_identity(task)
    curated_identity = curated._result_identity(task)

    assert no_skill.execution_fingerprint != curated.execution_fingerprint
    assert no_skill.ablation_execution_fingerprint == curated.ablation_execution_fingerprint
    assert no_identity["skill_mode"] == "no_skill"
    assert no_identity["skill_applied"] is False
    assert curated_identity["skill_mode"] == "curated_skill"
    assert curated_identity["skill_applied"] is True
    assert no_identity["skill_digest"] == curated_identity["skill_digest"]
    assert no_identity["variant_digest"] == curated_identity["variant_digest"]


def test_skill_ablation_requires_exact_variant_and_reports_lift() -> None:
    rows = [
        _row("no_skill", score=40, success=False),
        _row("curated_skill", score=100, success=True),
        _row("no_skill", score=80, success=True, repeat=2, digest="repeat-2"),
        _row("curated_skill", score=90, success=True, repeat=2, digest="repeat-2"),
    ]

    comparisons = skill_ablation_pairs(rows)

    assert len(comparisons) == 1
    item = comparisons[0]
    assert item["comparable"] is True
    assert item["matched_observations"] == 2
    assert item["mean_skill_lift"] == 35
    assert item["median_skill_lift"] == 35
    assert item["curated_wins"] == 2
    assert item["no_skill_wins"] == 0
    assert item["curated_pass_no_skill_fail"] == 1
    assert item["mean_input_token_delta"] == 40
    assert item["mean_output_token_delta"] == -5
    assert item["no_skill_execution_fingerprints"] == ["profile-no_skill"]
    assert item["curated_skill_execution_fingerprints"] == ["profile-curated_skill"]


def test_skill_ablation_does_not_pair_variant_mismatch() -> None:
    comparisons = skill_ablation_pairs([
        _row("no_skill", score=40, success=False, digest="a"),
        _row("curated_skill", score=100, success=True, digest="b"),
    ])

    assert len(comparisons) == 1
    assert comparisons[0]["comparable"] is True
    assert comparisons[0]["matched_observations"] == 0
    assert comparisons[0]["mean_skill_lift"] is None


def test_skill_ablation_fails_closed_on_model_or_profile_mismatch() -> None:
    model_mismatch = skill_ablation_pairs([
        _row("no_skill", score=40, success=False, model_fp="a"),
        _row("curated_skill", score=100, success=True, model_fp="b"),
    ])
    profile_mismatch = skill_ablation_pairs([
        _row("no_skill", score=40, success=False, ablation_fp="a"),
        _row("curated_skill", score=100, success=True, ablation_fp="b"),
    ])

    assert model_mismatch[0]["comparable"] is False
    assert model_mismatch[0]["reason"] == "model_identity_mismatch_or_unverified"
    assert profile_mismatch[0]["comparable"] is False
    assert profile_mismatch[0]["reason"] == "ablation_execution_profile_mismatch"
