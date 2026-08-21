import json
from pathlib import Path

from aios_bench.experiments import (
    annotate_experiment,
    annotate_repeat,
    make_experiment_id,
    matched_schedule,
)


def test_repeat_annotation_updates_manifest_and_rows(tmp_path: Path):
    (tmp_path / "run.json").write_text(json.dumps({"run_id": "r"}), encoding="utf-8")
    (tmp_path / "results.jsonl").write_text(json.dumps({"task_id": "t", "score": 100}) + "\n", encoding="utf-8")
    annotate_repeat(tmp_path, repeat=2, orchestration_seed=43)
    metadata = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    row = json.loads((tmp_path / "results.jsonl").read_text(encoding="utf-8"))
    assert metadata["repeat"] == row["repeat"] == 2
    assert metadata["orchestration_seed"] == row["orchestration_seed"] == 43
    assert metadata["experiment_schema"] == "aios-bench/experiment/v2"
    assert metadata["schedule_mode"] == "sequential"


def test_experiment_ids_are_suite_aware():
    assert make_experiment_id().endswith("_frontier-v3-exp")
    assert make_experiment_id("frontier_v4").endswith("_frontier-v4-exp")


def test_matched_schedule_is_deterministic_and_task_scoped():
    tasks = ["autonomy_001", "coding_001", "memory_001"]
    harnesses = ["hermes", "piagent", "opencode", "goose"]
    first = matched_schedule(tasks, harnesses, 42)
    second = matched_schedule(tasks, harnesses, 42)
    assert first == second
    assert [block.task_id for block in first] == tasks
    assert all(sorted(block.harness_order) == sorted(harnesses) for block in first)
    assert len({block.block_seed for block in first}) == len(tasks)
    assert len({block.task_seed for block in first}) == len(tasks)


def test_matched_annotation_adds_block_and_strict_model_identity(tmp_path: Path):
    schedule = matched_schedule(["autonomy_001"], ["hermes", "piagent"], 42)
    metadata = {
        "run_id": "r",
        "manifest": {"model": {"identity_fingerprint": "model-fp", "strictly_comparable": True}},
    }
    (tmp_path / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    (tmp_path / "results.jsonl").write_text(
        json.dumps({"task_id": "autonomy_001", "score": 100}) + "\n",
        encoding="utf-8",
    )
    annotate_experiment(
        tmp_path,
        experiment_id="exp-1",
        repeat=1,
        orchestration_seed=42,
        schedule_mode="matched_interleaved",
        task_blocks={schedule[0].task_id: schedule[0]},
    )
    row = json.loads((tmp_path / "results.jsonl").read_text(encoding="utf-8"))
    assert row["experiment_id"] == "exp-1"
    assert row["schedule_mode"] == "matched_interleaved"
    assert row["task_seed"] == schedule[0].task_seed
    assert row["block_seed"] == schedule[0].block_seed
    assert row["model_identity_fingerprint"] == "model-fp"
    assert row["model_strictly_comparable"] is True
