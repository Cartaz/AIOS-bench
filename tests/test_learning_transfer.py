from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aios_bench.materialization import ParametricTaskMaterializer
from aios_bench.parametric import (
    LearningTransferPressure,
    evaluate_variant,
    materialize_variant,
)
from aios_bench.parametric_goldens import materialize_parametric_golden
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"


def _learning_tasks():
    return [
        task
        for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.category == "learning"
    ]


def _oracle(run_dir: Path, task_id: str) -> dict:
    return json.loads(
        (run_dir / "oracles" / f"{task_id}.json").read_text(encoding="utf-8")
    )


def test_learning_acquisition_is_seeded_identifiable_and_strict(tmp_path: Path) -> None:
    pressure = LearningTransferPressure(
        demo_count=3,
        rows_per_demo=54,
        evaluation_rows=60,
        group_count=6,
        distractor_columns=4,
        schema_shift_fields=4,
    )
    context = {"phase": "acquire", "state_scope": "learning_transfer_v1"}
    first = tmp_path / "first"
    second = tmp_path / "second"
    oracle_a = materialize_variant(
        "learning_transfer",
        first,
        seed=123,
        parameters=pressure.to_dict(),
        context=context,
    )
    oracle_b = materialize_variant(
        "learning_transfer",
        second,
        seed=123,
        parameters=pressure.to_dict(),
        context=context,
    )

    assert oracle_a["variant_digest"] == oracle_b["variant_digest"]
    assert oracle_a["expected_skill"] == oracle_b["expected_skill"]
    assert oracle_a["identifiable_candidate_count"] == 1

    materialize_parametric_golden("learning_transfer", first, oracle_a)
    assert evaluate_variant("learning_transfer", first, oracle_a).passed is True

    skill_path = first / "skills" / "reporting_workflow.json"
    skill = json.loads(skill_path.read_text(encoding="utf-8"))
    skill["rules"]["required_status"] = "tampered"
    skill_path.write_text(json.dumps(skill), encoding="utf-8")
    grade = evaluate_variant("learning_transfer", first, oracle_a)
    assert grade.passed is False
    assert "canonical reusable procedure" in grade.detail


def test_learning_acquisition_teaching_set_is_identifiable_across_seeds(tmp_path: Path) -> None:
    for seed in range(12):
        oracle = materialize_variant(
            "learning_transfer",
            tmp_path / str(seed),
            seed=seed,
            context={"phase": "acquire", "state_scope": "learning_transfer_v1"},
        )
        assert oracle["identifiable_candidate_count"] == 1


def test_learning_state_flows_across_distinct_seed_warm_tasks(tmp_path: Path) -> None:
    tasks = _learning_tasks()
    assert [task.id for task in tasks] == [
        "learning_acquire_001",
        "learning_transfer_001",
        "learning_repair_001",
    ]
    runner = SimpleNamespace(repo_root=ROOT, run_dir=tmp_path / "run")
    materializer = ParametricTaskMaterializer(base_seed=42)
    acquire, transfer, repair = tasks

    acquire_workspace = materializer.prepare(runner, acquire)
    acquire_oracle = _oracle(runner.run_dir, acquire.id)
    materialize_parametric_golden("learning_transfer", acquire_workspace, acquire_oracle)
    acquired_skill = json.loads(
        (acquire_workspace / "skills" / "reporting_workflow.json").read_text(encoding="utf-8")
    )
    materializer.after_task(runner, acquire)

    transfer_workspace = materializer.prepare(runner, transfer)
    transfer_oracle = _oracle(runner.run_dir, transfer.id)
    assert transfer_oracle["seed"] != acquire_oracle["seed"]
    assert transfer_oracle["expected_skill"]["rules"] == acquired_skill["rules"]
    assert transfer_oracle["expected_skill"]["columns"] != acquired_skill["columns"]
    materialize_parametric_golden("learning_transfer", transfer_workspace, transfer_oracle)
    transferred_skill = json.loads(
        (transfer_workspace / "skills" / "reporting_workflow.json").read_text(encoding="utf-8")
    )
    materializer.after_task(runner, transfer)

    repair_workspace = materializer.prepare(runner, repair)
    repair_oracle = _oracle(runner.run_dir, repair.id)
    assert repair_oracle["seed"] not in {acquire_oracle["seed"], transfer_oracle["seed"]}
    assert repair_oracle["expected_skill"] == transferred_skill
    corrupted_skill = json.loads(
        (repair_workspace / "skills" / "reporting_workflow.json").read_text(encoding="utf-8")
    )
    correction = repair_oracle["correction"]
    field = correction["field"]
    assert corrupted_skill["rules"][field] == correction["previous"]
    assert transferred_skill["rules"][field] == correction["current"]

    materialize_parametric_golden("learning_transfer", repair_workspace, repair_oracle)
    assert evaluate_variant("learning_transfer", repair_workspace, repair_oracle).passed is True


def test_learning_pressure_rejects_non_identifiable_demo_size() -> None:
    with pytest.raises(ValueError, match="rows_per_demo"):
        LearningTransferPressure(rows_per_demo=47)
