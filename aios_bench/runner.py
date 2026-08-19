from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .adapters import ADAPTERS, Adapter, PiAgentAdapter
from .evaluators import evaluate_artifacts
from .models import Task, Trajectory
from .pi_rpc import PiRPCClient
from .retention import prune_run_artifacts
from .scoring import overall_score
from .telemetry import parse_output


@dataclass(frozen=True)
class AgentConfig:
    name: str
    display_name: str
    adapter: Adapter


AGENTS = {
    name: AgentConfig(name, {
        "codex": "Codex",
        "hermes": "Hermes Agent", "piagent": "Pi Agent", "opencode": "OpenCode",
        "goose": "Goose", "letta": "Letta", "agentzero": "Agent Zero",
    }[name], adapter)
    for name, adapter in ADAPTERS.items()
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _git_commit(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _suite_revision(repo_root: Path) -> str:
    catalog = repo_root / "benchmarks" / "tasks" / "frontier_v2.json"
    return hashlib.sha256(catalog.read_bytes()).hexdigest()


def _safe_run_id(value: str) -> str:
    cleaned = value.strip().replace("/", "_").replace("\\", "_")
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("run_id must not be empty")
    return cleaned


class BenchmarkRunner:
    def __init__(self, repo_root: Path, agent: AgentConfig, results_dir: Path,
                 task_timeout: float, total_timeout: float | None, resume: bool = True,
                 model: str = "unknown", keep_raw: bool = False, run_id: str | None = None) -> None:
        self.repo_root = repo_root
        self.agent = agent
        self.results_dir = results_dir
        self.task_timeout = task_timeout
        self.total_timeout = total_timeout
        self.resume = resume
        self.model = model
        self.keep_raw = keep_raw
        self.model_dir = results_dir / agent.name / model.replace("/", "_")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        if run_id is None:
            timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S")
            run_id = f"{timestamp}_frontier-v2"
        self.run_id = _safe_run_id(run_id)
        self.run_dir = self.model_dir / "runs" / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint = self.run_dir / "results.jsonl"
        self.events = self.run_dir / "events.jsonl"
        self.metadata_path = self.run_dir / "run.json"
        self._write_metadata()
        self._update_latest_pointer()

    def _write_metadata(self, finished_at: str | None = None) -> None:
        existing: dict = {}
        if self.metadata_path.exists():
            try:
                existing = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        metadata = {
            "benchmark": "AIOS-bench",
            "suite": "frontier_v2",
            "suite_revision": _suite_revision(self.repo_root),
            "harness": self.agent.name,
            "model": self.model,
            "model_id": self.model,
            "run_id": self.run_id,
            "started_at": existing.get("started_at", _utc_now()),
            "git_commit": _git_commit(self.repo_root),
            "task_count": len(self._catalog_task_count()),
        }
        if finished_at is not None:
            metadata["finished_at"] = finished_at
        elif existing.get("finished_at"):
            metadata["finished_at"] = existing["finished_at"]
        self.metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _catalog_task_count(self) -> list[str]:
        catalog = self.repo_root / "benchmarks" / "tasks" / "frontier_v2.json"
        return [str(item["id"]) for item in json.loads(catalog.read_text(encoding="utf-8"))]

    def _update_latest_pointer(self) -> None:
        latest = self.model_dir / "latest"
        try:
            if latest.is_symlink() or latest.exists():
                if latest.is_dir() and not latest.is_symlink():
                    shutil.rmtree(latest)
                else:
                    latest.unlink()
            latest.symlink_to(self.run_dir, target_is_directory=True)
            fallback = self.model_dir / "latest.txt"
            if fallback.exists():
                fallback.unlink()
        except OSError:
            (self.model_dir / "latest.txt").write_text(self.run_id + "\n", encoding="utf-8")

    def completed(self, tasks: list[Task]) -> set[str]:
        if not self.resume or not self.checkpoint.exists():
            return set()
        revisions = {t.id: t.revision for t in tasks}
        done: set[str] = set()
        for line in self.checkpoint.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if (
                    item.get("status") == "completed"
                    and revisions.get(item.get("task_id")) == item.get("task_revision", 1)
                    and item.get("suite_revision") == self._current_suite_revision()
                ):
                    done.add(item["task_id"])
        return done

    def _current_suite_revision(self) -> str:
        """Fingerprint used to decide whether a checkpoint can be resumed."""
        return _suite_revision(self.repo_root)

    def _log(self, event: dict) -> None:
        with self.events.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": time.time(), "run_id": self.run_id, **event}, ensure_ascii=False) + "\n")

    def _write_result(self, item: dict) -> None:
        with self.checkpoint.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def _workspace(self, task: Task) -> Path:
        path = self.run_dir / "workspaces" / task.id
        if path.exists():
            shutil.rmtree(path)
        source = self.repo_root / "benchmarks" / "fixtures" / "workspace"
        shutil.copytree(source, path)
        return path

    def run_task(self, task: Task, timeout: float) -> Trajectory:
        workspace = self._workspace(task)
        logs = self.run_dir / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        stdout_path = logs / f"{task.id}.stdout.log"
        stderr_path = logs / f"{task.id}.stderr.log"
        prompt = (
            "You are being evaluated by AIOS-bench. Work only inside the provided workspace. "
            "Complete the task fully, verify the result, and do not modify benchmark files outside "
            "the workspace.\n\nTASK:\n" + task.prompt
        )
        invocation = self.agent.adapter.build(prompt, workspace, self.model)
        command = invocation.command
        custom = os.environ.get(f"AIOS_BENCH_{self.agent.name.upper()}_COMMAND")
        if custom:
            import shlex
            command = [*shlex.split(custom), prompt]
        env = os.environ.copy()
        env.update(invocation.environment)
        env.update({
            "AIOS_BENCH_TASK_ID": task.id, "AIOS_BENCH_AGENT": self.agent.name,
            "AIOS_BENCH_MODEL": self.model, "AIOS_BENCH_RUN_ID": self.run_id,
            "AIOS_BENCH_FIXTURE_ROOT": str(self.repo_root / "benchmarks" / "fixtures" / "workspace"),
        })
        # Reference evaluators use the current process environment as well as
        # the child-agent environment. Keep both views consistent.
        os.environ.update({
            "AIOS_BENCH_TASK_ID": task.id, "AIOS_BENCH_AGENT": self.agent.name,
            "AIOS_BENCH_MODEL": self.model, "AIOS_BENCH_RUN_ID": self.run_id,
            "AIOS_BENCH_FIXTURE_ROOT": str(self.repo_root / "benchmarks" / "fixtures" / "workspace"),
        })
        self._log({"event": "task_started", "task_id": task.id, "command": command,
                   "model": self.model, "tier": task.tier, "task_revision": task.revision})
        started = time.monotonic()
        trajectory = Trajectory(agent=self.agent.name, task_id=task.id)
        status = "completed"
        try:
            if isinstance(self.agent.adapter, PiAgentAdapter):
                result = PiRPCClient(self.model, workspace, timeout, environment=env).run(prompt)
                stdout_path.write_text(result.stdout, encoding="utf-8")
                stderr_path.write_text(result.stderr, encoding="utf-8")
                if result.timed_out:
                    status = "timeout"
                    trajectory.errors = 1
                    trajectory.events.append({"type": "error", "message": "Pi RPC task timeout"})
                else:
                    trajectory.success = result.returncode == 0
                    if result.returncode != 0:
                        status = "failed"
                        trajectory.errors = 1
            else:
                with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
                    proc = subprocess.run(command, cwd=workspace, env=env, stdout=out, stderr=err,
                                          text=True, timeout=timeout, check=False)
                trajectory.success = proc.returncode == 0
                if proc.returncode != 0:
                    status = "failed"
                    trajectory.errors = 1
        except subprocess.TimeoutExpired:
            status = "timeout"
            trajectory.errors = 1
        except FileNotFoundError as exc:
            status = "error"
            trajectory.errors = 1
            trajectory.events.append({"type": "agent_not_found", "error": str(exc)})
        except Exception as exc:
            status = "error"
            trajectory.errors = 1
            trajectory.events.append({"type": "runner_error", "error": repr(exc)})
        trajectory.duration_seconds = time.monotonic() - started

        stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
        trajectory.apply_events([e.to_dict() for e in parse_output(stdout, stderr, source=self.agent.name)])
        if trajectory.errors and status == "completed":
            status = "failed"
            trajectory.success = False

        evaluation = None
        checks = list(task.acceptance)
        spec = self.repo_root / "benchmarks" / "tasks" / "specs" / f"{task.id}.json"
        if not checks and spec.is_file():
            checks = json.loads(spec.read_text(encoding="utf-8"))["checks"]
        if checks:
            evaluation = evaluate_artifacts(
                workspace, checks, run_dir=self.run_dir,
                events=trajectory.events,
            )
            trajectory.evaluation_score = float(evaluation["acceptance_score"])
            trajectory.success = trajectory.success and bool(evaluation["passed"])
            if not trajectory.success and status == "completed":
                status = "failed"
            trajectory.events.append({"type": "deterministic_evaluation", "result": evaluation})

        result = trajectory.to_dict()
        result.update({
            "status": status, "evaluation": evaluation, "score": overall_score(trajectory),
            "model": self.model, "harness": self.agent.name, "task_id": task.id,
            "task_revision": task.revision, "category": task.category, "tier": task.tier,
            "mode": task.mode, "run_id": self.run_id, "suite": "frontier_v2",
            "suite_revision": _suite_revision(self.repo_root), "git_commit": _git_commit(self.repo_root),
            "stdout": str(stdout_path), "stderr": str(stderr_path),
        })
        self._write_result(result)
        self._log({"event": "task_finished", "task_id": task.id, "success": trajectory.success,
                   "status": status, "duration": trajectory.duration_seconds, "score": result["score"],
                   "telemetry_available": trajectory.telemetry_available, "tier": task.tier})
        return trajectory

    def cleanup(self) -> dict[str, int | bool]:
        return prune_run_artifacts(self.run_dir, keep_raw=self.keep_raw)

    def run(self, tasks: list[Task]) -> int:
        done = self.completed(tasks)
        started = time.monotonic()
        remaining = [t for t in tasks if t.id not in done]
        print(f"AIOS-bench | {self.agent.display_name} | model={self.model} | run={self.run_id}")
        print(f"Tasks: {len(remaining)} (resume={'on' if self.resume else 'off'})")
        passed = 0
        scores: list[float] = []
        for index, task in enumerate(remaining, 1):
            timeout = self.task_timeout
            if self.total_timeout is not None:
                timeout = min(timeout, self.total_timeout - (time.monotonic() - started))
                if timeout <= 0:
                    self.cleanup()
                    self._write_metadata(_utc_now())
                    return 2
            print(f"[{index}/{len(remaining)}] {task.id} [T{task.tier}] ...", flush=True)
            trajectory = self.run_task(task, timeout)
            score = overall_score(trajectory)
            scores.append(score)
            if trajectory.success:
                passed += 1
            print(f"    {'PASS' if trajectory.success else 'FAIL'}  {score:.1f}/100  {trajectory.duration_seconds:.1f}s", flush=True)
        avg = sum(scores) / len(scores) if scores else 0.0
        cleanup = self.cleanup()
        self._write_metadata(_utc_now())
        print(f"\nResult: {passed}/{len(remaining)} passed | average score {avg:.1f}/100")
        if not self.keep_raw:
            print(f"Retention cleanup: removed {cleanup['files_removed']} files and {cleanup['dirs_removed']} dependency/cache directories")
        print(f"Results: {self.run_dir}")
        return 0 if passed == len(remaining) else 1
