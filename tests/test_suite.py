import json
from pathlib import Path

from aios_bench.cli import load_tasks
from benchmark.scoring import aggregate, evaluate


def test_pilot_has_24_tasks():
    tasks = load_tasks()
    assert len(tasks) == 24
    assert len({t["id"] for t in tasks}) == 24


def test_scoring_hard_gates_success():
    task = {"id":"x","category":"tool_use","evaluator":{"type":"trajectory"}}
    bad = evaluate(task, {"success":False,"errors":0}, Path("."))
    good = evaluate(task, {"success":True,"errors":0,"tool_calls":1}, Path("."))
    assert bad["passed"] is False
    assert good["passed"] is True
    assert good["quality_score"] > bad["quality_score"]


def test_aggregate():
    rows = [
        {"task_id":"a","category":"coding","passed":True,"quality_score":90},
        {"task_id":"b","category":"coding","passed":False,"quality_score":30},
    ]
    result = aggregate(rows)
    assert result["tasks"] == 2
    assert result["passed"] == 1
    assert result["by_category"]["coding"] == 60
