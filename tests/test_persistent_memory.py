from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from aios_bench.materialization import ParametricTaskMaterializer
from aios_bench.parametric import (
    PersistentMemoryPressure,
    evaluate_variant,
    materialize_variant,
)
from aios_bench.parametric_goldens import materialize_parametric_golden
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"


def _memory_tasks():
    return [
        task
        for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.category == "memory"
    ]


def _oracle(run_dir: Path, task_id: str) -> dict:
    return json.loads(
        (run_dir / "oracles" / f"{task_id}.json").read_text(encoding="utf-8")
    )


def test_persistent_memory_capture_is_seeded_and_strict(tmp_path: Path) -> None:
    pressure = PersistentMemoryPressure(
        durable_fact_count=7,
        transient_fact_count=4,
        distractor_fact_count=5,
        update_count=2,
    )
    context = {"phase": "capture", "state_scope": "persistent_memory_v1"}
    first = tmp_path / "first"
    second = tmp_path / "second"
    oracle_a = materialize_variant(
        "persistent_memory",
        first,
        seed=123,
        parameters=pressure.to_dict(),
        context=context,
    )
    oracle_b = materialize_variant(
        "persistent_memory",
        second,
        seed=123,
        parameters=pressure.to_dict(),
        context=context,
    )
    assert oracle_a["variant_digest"] == oracle_b["variant_digest"]
    assert oracle_a["expected_memory"] == oracle_b["expected_memory"]

    materialize_parametric_golden("persistent_memory", first, oracle_a)
    assert evaluate_variant("persistent_memory", first, oracle_a).passed is True

    memory_path = first / ".agent_memory" / "preferences.json"
    memory = json.loads(memory_path.read_text(encoding="utf-8"))
    memory["preferences"]["session_instruction_01"] = "should-not-persist"
    memory_path.write_text(json.dumps(memory), encoding="utf-8")
    grade = evaluate_variant("persistent_memory", first, oracle_a)
    assert grade.passed is False
    assert "canonical state" in grade.detail


def test_persistent_memory_state_flows_across_warm_tasks(tmp_path: Path) -> None:
    tasks = _memory_tasks()
    assert [task.id for task in tasks] == [
        "memory_persist_001",
        "memory_persist_002",
        "memory_persist_003",
    ]
    runner = SimpleNamespace(repo_root=ROOT, run_dir=tmp_path / "run")
    materializer = ParametricTaskMaterializer(base_seed=42)

    capture, apply, update = tasks
    capture_workspace = materializer.prepare(runner, capture)
    capture_oracle = _oracle(runner.run_dir, capture.id)
    materialize_parametric_golden(
        "persistent_memory",
        capture_workspace,
        capture_oracle,
    )
    captured_memory = json.loads(
        (capture_workspace / ".agent_memory" / "preferences.json").read_text(
            encoding="utf-8"
        )
    )
    materializer.after_task(runner, capture)

    apply_workspace = materializer.prepare(runner, apply)
    assert json.loads(
        (apply_workspace / ".agent_memory" / "preferences.json").read_text(
            encoding="utf-8"
        )
    ) == captured_memory
    apply_oracle = _oracle(runner.run_dir, apply.id)
    assert apply_oracle["expected_memory"] == captured_memory
    materialize_parametric_golden(
        "persistent_memory",
        apply_workspace,
        apply_oracle,
    )
    materializer.after_task(runner, apply)

    update_workspace = materializer.prepare(runner, update)
    update_oracle = _oracle(runner.run_dir, update.id)
    assert update_oracle["expected_memory"]["preferences"] != captured_memory["preferences"]
    assert len(update_oracle["expected_memory"]["history"]) == 2
    materialize_parametric_golden(
        "persistent_memory",
        update_workspace,
        update_oracle,
    )
    assert evaluate_variant(
        "persistent_memory",
        update_workspace,
        update_oracle,
    ).passed is True


def test_persistent_memory_apply_requires_preserved_memory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant(
        "persistent_memory",
        workspace,
        seed=99,
        context={"phase": "apply", "state_scope": "persistent_memory_v1"},
    )
    materialize_parametric_golden("persistent_memory", workspace, oracle)
    memory_path = workspace / ".agent_memory" / "preferences.json"
    memory = json.loads(memory_path.read_text(encoding="utf-8"))
    memory["preferences"]["primary_language"] = "tampered"
    memory_path.write_text(json.dumps(memory), encoding="utf-8")

    grade = evaluate_variant("persistent_memory", workspace, oracle)
    assert grade.passed is False
    assert "canonical state" in grade.detail
