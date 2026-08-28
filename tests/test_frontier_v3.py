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
        ROOT, AGENTS["piagent"], tmp_path, task_timeout=1, total_timeout=None,
        model="test", run_id="corpus-check",
    )
    workspace = runner._workspace(task)
    corpus = workspace / "research" / "long_horizon_corpus"
    assert corpus.is_dir()
    assert sum(path.stat().st_size for path in corpus.rglob("*") if path.is_file()) >= 50_000
    assert "Gate ID: LH-047" in (corpus / "packet_047.md").read_text(encoding="utf-8")
    outcomes = [
        subprocess.run([sys.executable, "tools/validator.py"], cwd=workspace, check=False).returncode
        for _ in range(4)
    ]
    assert outcomes == [0, 0, 1, 0]


def test_long_horizon_reference_oracle_checks_recovery_and_grounding(tmp_path: Path):
    task = next(task for task in load_tasks(ROOT / "benchmarks/tasks") if task.id == "long_horizon_001")
    runner = FrontierV3Runner(
        ROOT, AGENTS["piagent"], tmp_path, task_timeout=1, total_timeout=None,
        model="test", run_id="oracle-check",
    )
    workspace = runner._workspace(task)
    state = workspace / ".state"
    state.mkdir()
    for n in range(4):
        subprocess.run([sys.executable, "tools/validator.py"], cwd=workspace, check=False)
    for n in (1, 3, 5):
        (state / f"checkpoint_{n}.json").write_text("{}", encoding="utf-8")
    (workspace / "reports").mkdir()
    (workspace / "reports/long_horizon_changelog.md").write_text(
        "validator state corruption\nRecovery: rerun\nLH-047, 240 ms, Priya N.\n",
        encoding="utf-8",
    )
    passed, detail = check_long(task.id, workspace, ROOT / "benchmarks/fixtures/workspace")
    assert passed, detail


def test_frontier_v3_resume_rejects_results_from_another_suite_revision(tmp_path: Path):
    tasks = load_tasks(ROOT / "benchmarks/tasks")
    runner = FrontierV3Runner(
        ROOT, AGENTS["piagent"], tmp_path, task_timeout=1, total_timeout=None,
        model="test", run_id="resume-check",
    )
    task = tasks[0]
    runner.checkpoint.write_text(json.dumps({
        "task_id": task.id,
        "task_revision": task.revision,
        "status": "completed",
        "suite_revision": "obsolete",
    }) + "\n", encoding="utf-8")
    assert task.id not in runner.completed(tasks)

    runner.checkpoint.write_text(json.dumps({
        "task_id": task.id,
        "task_revision": task.revision,
        "status": "completed",
        "suite_revision": runner._revision(),
    }) + "\n", encoding="utf-8")
    assert task.id in runner.completed(tasks)


def test_suite_revision_auto_discovers_execution_and_scoring_semantics():
    paths = semantic_source_paths(ROOT)
    names = {path.name for path in paths}
    assert {
        "runner.py", "adapters.py", "sandbox.py", "scoring.py", "telemetry.py",
        "experiments.py", "scheduler.py", "failures.py", "task_execution.py",
        "materialization.py", "suites.py", "processes.py",
    } <= names
    assert any("server_metrics" in path.parts for path in paths)
    assert "doctor.py" not in names
