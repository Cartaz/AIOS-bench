import json
from pathlib import Path

from aios_bench.tasks import load_tasks

ROOT=Path(__file__).resolve().parents[1]


def test_frontier_v3_has_28_unique_tasks():
    tasks=load_tasks(ROOT/'benchmarks/tasks')
    assert len(tasks)==28
    assert len({t.id for t in tasks})==28
    assert all(t.revision==3 for t in tasks)


def test_frontier_v3_uses_reference_checks():
    tasks=load_tasks(ROOT/'benchmarks/tasks')
    for task in tasks:
        refs=[c for c in task.acceptance if c['type']=='reference']
        assert len(refs)==1, task.id
        assert refs[0]['task_id']==task.id


def test_frontier_v3_catalog_is_split_by_category():
    files=sorted((ROOT/'benchmarks/tasks/frontier_v3').glob('*.json'))
    assert [p.stem for p in files]==['autonomy','browser','coding','knowledge','learning','long_horizon','memory','subagents','tool_use']
    assert all(isinstance(json.loads(p.read_text()),list) for p in files)
