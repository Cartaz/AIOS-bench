import json
from types import SimpleNamespace

from aios_bench.models import Task, Trajectory
from aios_bench.runtime_readiness import RuntimeReadiness
from aios_bench.scheduler import MatchedInterleavedScheduler


class _Adapter:
    def assess_task(self, task):
        return SimpleNamespace(is_supported=True, missing=frozenset(), to_dict=lambda: {})


class _Runner:
    def __init__(self, root, name, readiness=None):
        self.agent = SimpleNamespace(name=name, display_name=name, adapter=_Adapter())
        self.run_dir = root / name
        self.run_dir.mkdir()
        self.task_timeout = 30.0
        self.total_timeout = None
        self.keep_raw = True
        self.results = {}
        self.calls = []
        self.probe_calls = 0
        self.readiness = readiness or RuntimeReadiness(
            True,
            "ready",
            "test runtime ready",
            0.1,
            returncode=0,
        )
        (self.run_dir / "run.json").write_text(json.dumps({
            "run_id": "run",
            "manifest": {"model": {"identity_fingerprint": "same-model", "strictly_comparable": True}},
        }), encoding="utf-8")

    def completed(self, tasks):
        return {
            task.id
            for task in tasks
            if self.results.get(task.id, {}).get("status") in {"completed", "unsupported"}
        }

    def latest_results(self):
        return dict(self.results)

    def runtime_readiness(self):
        self.probe_calls += 1
        return self.readiness

    def record_unsupported(self, task, assessment):
        raise AssertionError("unexpected unsupported task")

    def _store_row(self, row):
        self.results[row["task_id"]] = row
        with (self.run_dir / "results.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")

    def record_noncomparable(self, task, status, reason, assessment):
        self._store_row({
            "harness": self.agent.name,
            "model": "model",
            "suite": "frontier_v3",
            "suite_revision": "rev",
            "task_id": task.id,
            "status": status,
            "failure_kind": "BLOCKED" if status == "blocked" else status.upper(),
            "success": False,
            "score": None,
            "comparable": False,
            "reason": reason,
        })

    def run_task(self, task, timeout):
        self.calls.append(task.id)
        trajectory = Trajectory(
            agent=self.agent.name,
            task_id=task.id,
            success=True,
            duration_seconds=1.0,
            evaluation_score=1.0,
        )
        row = {
            "harness": self.agent.name,
            "model": "model",
            "suite": "frontier_v3",
            "suite_revision": "rev",
            "task_id": task.id,
            "status": "completed",
            "success": True,
            "score": 100.0,
            "comparable": True,
        }
        self._store_row(row)
        return trajectory

    def finalize(self, tasks, *, status, finished_at):
        attempted = [row for row in self.results.values() if row.get("status") != "blocked"]
        counts = {
            "supported_task_count": len(tasks),
            "unsupported_task_count": 0,
            "completed_task_count": len(self.results),
            "attempted_task_count": len(attempted),
            "passed_task_count": sum(bool(row.get("success")) for row in attempted),
            "blocked_task_count": sum(
                row.get("status") == "blocked" for row in self.results.values()
            ),
        }
        path = self.run_dir / "run.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata.update(counts)
        metadata["status"] = status
        metadata["finished_at"] = finished_at
        path.write_text(json.dumps(metadata), encoding="utf-8")
        return {
            "cleanup": {"files_removed": 0, "dirs_removed": 0},
            "counts": counts,
            "latest": self.latest_results(),
        }

    def abort(self, tasks):
        self.finalize(tasks, status="aborted", finished_at="")


def test_scheduler_executes_every_task_as_a_matched_block(tmp_path):
    tasks = [Task("task_a", "coding", "a"), Task("task_b", "coding", "b")]
    runners = {name: _Runner(tmp_path, name) for name in ("hermes", "piagent", "opencode")}
    scheduler = MatchedInterleavedScheduler(
        runners,
        tasks,
        experiment_id="exp-1",
        repeat=1,
        orchestration_seed=42,
    )
    result = scheduler.run()
    assert result.exit_code == 0
    assert len(result.blocks) == 2
    for runner in runners.values():
        assert runner.probe_calls == 1
        assert runner.calls == ["task_a", "task_b"]
        rows = [json.loads(line) for line in (runner.run_dir / "results.jsonl").read_text().splitlines()]
        assert [row["task_id"] for row in rows] == ["task_a", "task_b"]
        assert all(row["schedule_mode"] == "matched_interleaved" for row in rows)
        assert all(row["experiment_id"] == "exp-1" for row in rows)
        assert all(row["model_identity_fingerprint"] == "same-model" for row in rows)


def test_scheduler_blocks_nonready_harness_without_running_or_scoring_it(tmp_path):
    task = Task("task_a", "coding", "a")
    blocked = RuntimeReadiness(
        False,
        "process_exit",
        "runtime probe exited with code 1",
        0.2,
        returncode=1,
        stdout="probe.stdout.log",
        stderr="probe.stderr.log",
    )
    runners = {
        "ready": _Runner(tmp_path, "ready"),
        "blocked": _Runner(tmp_path, "blocked", readiness=blocked),
    }
    result = MatchedInterleavedScheduler(
        runners,
        [task],
        experiment_id="exp-blocked",
        repeat=1,
        orchestration_seed=42,
    ).run()

    assert result.exit_code == 1
    assert runners["ready"].calls == ["task_a"]
    assert runners["blocked"].calls == []
    assert runners["ready"].probe_calls == 1
    assert runners["blocked"].probe_calls == 1

    row = runners["blocked"].latest_results()["task_a"]
    assert row["status"] == "blocked"
    assert row["failure_kind"] == "BLOCKED"
    assert row["score"] is None
    assert row["comparable"] is False
    assert row["reason"]["runtime_readiness"]["kind"] == "process_exit"
