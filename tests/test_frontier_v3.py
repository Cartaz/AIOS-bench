import json
import subprocess
import sys
from pathlib import Path

from aios_bench.frontier_runner import semantic_source_paths
from aios_bench.frontier_v3_runner import FrontierV3Runner
from aios_bench.reference_checks_long import check as check_long
from aios_bench.runner import AGENTS
from aios_bench.tasks import load_tasks

ROOT=Path(__file__).resolve().parents[1]


def test_frontier_v3_has_28_unique_tasks():
    tasks=load_tasks(ROOT/'benchmarks/tasks')
    assert len(tasks)==28
    assert len({t.id for t in tasks})==28
    assert all(t.revision >= 3 for t in tasks)
    assert next(t for t in tasks if t.id == "long_horizon_001").revision == 6


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


def test_long_horizon_workspace_contains_the_declared_large_corpus(tmp_path: Path):
    tasks = load_tasks(ROOT / "benchmarks/tasks")
    task = next(task for task in tasks if task.id == "long_horizon_001")
    runner = FrontierV3Runner(
        ROOT,
        AGENTS["piagent"],
        tmp_path,
        task_timeout=1,
        total_timeout=None,
        model="test",
        run_id="large-corpus",
    )
    workspace = runner._workspace(task)
    corpus = workspace / "research" / "long_horizon_corpus"
    files = list(corpus.glob("*.md"))
    total_bytes = sum(path.stat().st_size for path in files)
    assert len(files) >= 35
    assert total_bytes >= 80000
    assert (corpus / "manifest.json").is_file()


def test_long_horizon_reference_requires_recovery_and_final_release_gate(tmp_path: Path):
    workspace = tmp_path / "workspace"
    subprocess.run(
        [sys.executable, "-c", (
            "from pathlib import Path; "
            "from aios_bench.fixtures import materialize_long_horizon_corpus; "
            "materialize_long_horizon_corpus(Path(r'" + str(workspace) + "'))"
        )],
        cwd=ROOT,
        check=True,
    )
    state = workspace / ".state"
    state.mkdir(parents=True, exist_ok=True)
    for index in (1, 3, 5):
        (state / f"checkpoint_{index}.json").write_text(
            json.dumps({"stage": index, "status": "complete"}),
            encoding="utf-8",
        )
    reports = workspace / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "long_horizon_changelog.md").write_text(
        "Final signed release gate: packet LH-204, latency budget 180ms, rollback owner Mira Chen.\n"
        "The provisional packet LH-203 was superseded.\n",
        encoding="utf-8",
    )

    ok, detail = check_long("long_horizon_001", workspace)
    assert ok is False
    assert "recovery" in detail.lower()

    marker = workspace / ".validator_state.json"
    marker.write_text(json.dumps({"failures_seen": 1, "recovered": True}), encoding="utf-8")
    ok, detail = check_long("long_horizon_001", workspace)
    assert ok is True, detail


def test_frontier_v3_semantic_fingerprint_auto_discovers_execution_sources():
    paths = semantic_source_paths(ROOT)
    names = {path.name for path in paths}
    assert "frontier_runner.py" in names
    assert "task_execution.py" in names
    assert "materialization.py" in names
    assert "suites.py" in names
