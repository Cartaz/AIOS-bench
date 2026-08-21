from __future__ import annotations

import json
from pathlib import Path

from aios_bench.raw import ATTEMPT_SCHEMA, latest_attempts, load_attempts, source_index


def _run(root: Path) -> Path:
    directory = root / "piagent" / "ornith" / "runs" / "run-1"
    directory.mkdir(parents=True)
    (directory / "run.json").write_text(
        json.dumps({
            "harness": "piagent",
            "model": "ornith",
            "run_id": "run-1",
            "suite": "frontier_v3",
            "suite_revision": "rev",
            "status": "completed",
            "task_count": 2,
        }),
        encoding="utf-8",
    )
    return directory


def test_raw_loader_preserves_every_attempt_and_derives_identity(tmp_path: Path) -> None:
    directory = _run(tmp_path)
    rows = [
        {"task_id": "task-a", "score": 10, "attempt_id": "spoof", "attempt_index": 99},
        {"task_id": "task-a", "score": 90, "source_path": "spoofed"},
        {"task_id": "task-b", "score": 50},
    ]
    (directory / "results.jsonl").write_text(
        json.dumps(rows[0]) + "\n" + "not-json\n" + json.dumps(rows[1]) + "\n" + json.dumps(rows[2]) + "\n",
        encoding="utf-8",
    )

    attempts = load_attempts(tmp_path)

    assert len(attempts) == 3
    task_a = [row for row in attempts if row["task_id"] == "task-a"]
    assert [row["attempt_index"] for row in task_a] == [1, 2]
    assert task_a[0]["attempt_id"] != "spoof"
    assert task_a[0]["attempt_id"] != task_a[1]["attempt_id"]
    assert all(row["attempt_schema"] == ATTEMPT_SCHEMA for row in attempts)
    assert task_a[1]["source_path"].endswith("runs/run-1/results.jsonl")
    assert task_a[1]["source_line"] == 3
    assert all(row["harness"] == "piagent" for row in attempts)
    assert all(row["model"] == "ornith" for row in attempts)

    latest = latest_attempts(attempts)
    by_task = {row["task_id"]: row for row in latest}
    assert by_task["task-a"]["score"] == 90
    assert by_task["task-a"]["attempt_index"] == 2
    assert by_task["task-b"]["attempt_index"] == 1


def test_source_index_hashes_only_analysis_inputs(tmp_path: Path) -> None:
    directory = _run(tmp_path)
    results = directory / "results.jsonl"
    results.write_text(json.dumps({"task_id": "task-a", "score": 10}) + "\n", encoding="utf-8")

    first = source_index(tmp_path)
    (directory / "workspace-artifact.txt").write_text("not an analysis input", encoding="utf-8")
    second = source_index(tmp_path)
    assert first["digest"] == second["digest"]
    assert first["file_count"] == 2

    results.write_text(results.read_text(encoding="utf-8") + json.dumps({"task_id": "task-a", "score": 20}) + "\n", encoding="utf-8")
    third = source_index(tmp_path)
    assert third["digest"] != first["digest"]
