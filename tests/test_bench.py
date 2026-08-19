import json
from pathlib import Path

from aios_bench.models import load_tasks


def test_pilot_is_valid():
    tasks = load_tasks()
    assert len(tasks) == 24
    assert len({t.id for t in tasks}) == len(tasks)
    assert {t.category for t in tasks} == {
        "tool_use", "knowledge", "memory", "learning", "coding",
        "autonomy", "browser", "long_horizon"
    }


def test_trajectory_schema_matches_model(tmp_path):
    p = tmp_path / "trajectory.jsonl"
    p.write_text(json.dumps({"agent":"x","task_id":"x","success":True}) + "\n")
    from aios_bench.models import load_trajectory
    assert load_trajectory(p)[0].success is True
