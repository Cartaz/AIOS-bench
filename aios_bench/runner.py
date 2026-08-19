from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .evaluators import evaluate_json
from .models import Task, Trajectory


@dataclass(frozen=True)
class AgentConfig:
    name: str
    command: tuple[str, ...]


AGENTS = {
    "hermes": AgentConfig("hermes", ("hermes", "chat", "-q")),
    "pi": AgentConfig("pi", ("pi", "-p")),
}


class BenchmarkRunner:
    def __init__(
        self,
        repo_root: Path,
        agent: AgentConfig,
        results_dir: Path,
        task_timeout: float,
        total_timeout: float | None,
        resume: bool = True,
    ) -> None:
        self.repo_root = repo_root
        self.agent = agent
        self.results_dir = results_dir
        self.task_timeout = task_timeout
        self.total_timeout = total_timeout
        self.resume = resume
        self.run_dir = results_dir / agent.name
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint = self.run_dir / "results.jsonl"
        self.events = self.run_dir / "events.jsonl"

    def completed(self) -> set[str]:
        if not self.resume or not self.checkpoint.exists():
            return set()
        done: set[str] = set()
        for line in self.checkpoint.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("status") == "completed":
                done.add(item["task_id"])
        return done

    def _log(self, event: dict) -> None:
        event = {"timestamp": time.time(), **event}
        with self.events.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

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
        stdout_path = self.run_dir / "logs" / f"{task.id}.stdout.log"
        stderr_path = self.run_dir / "logs" / f"{task.id}.stderr.log"
        stdout_path.parent.mkdir(parents=True, exist_ok=True)

        prompt = (
            "You are being evaluated by AIOS-bench. Work only inside the provided workspace. "
            "Complete the task fully, verify the result, and do not modify benchmark files outside "
            "the workspace.\n\nTASK:\n" + task.prompt
        )
        command = [*self.agent.command, prompt]
        env = os.environ.copy()
        env["AIOS_BENCH_TASK_ID"] = task.id
        env["AIOS_BENCH_WORKSPACE"] = str(workspace.resolve())
        env["AIOS_BENCH_AGENT"] = self.agent.name

        self._log({"event": "task_started", "task_id": task.id, "command": command})
        started = time.monotonic()
        trajectory = Trajectory(agent=self.agent.name, task_id=task.id)
        status = "completed"
        try:
            with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
                proc = subprocess.run(
                    command,
                    cwd=workspace,
                    env=env,
                    stdout=out,
                    stderr=err,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
            trajectory.success = proc.returncode == 0
            if proc.returncode != 0:
                status = "failed"
                trajectory.errors = 1
                trajectory.events.append({"type": "process_exit", "returncode": proc.returncode})
        except subprocess.TimeoutExpired:
            status = "timeout"
            trajectory.errors = 1
            trajectory.events.append({"type": "timeout", "seconds": timeout})
        except FileNotFoundError as exc:
            status = "error"
            trajectory.errors = 1
            trajectory.events.append({"type": "agent_not_found", "error": str(exc)})
        except Exception as exc:
            status = "error"
            trajectory.errors = 1
            trajectory.events.append({"type": "runner_error", "error": repr(exc)})
        trajectory.duration_seconds = time.monotonic() - started

        spec = self.repo_root / "benchmarks" / "tasks" / "specs" / f"{task.id}.json"
        evaluation = None
        if spec.is_file():
            evaluation = evaluate_json(workspace, spec)
            trajectory.success = trajectory.success and bool(evaluation["passed"])
            if not trajectory.success and status == "completed":
                status = "failed"
            trajectory.events.append({"type": "deterministic_evaluation", "result": evaluation})

        result = trajectory.to_dict()
        result.update({
            "status": status,
            "evaluation": evaluation,
            "workspace": str(workspace),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
        })
        self._write_result(result)
        self._log({"event": "task_finished", "task_id": task.id, "success": trajectory.success, "status": status, "duration": trajectory.duration_seconds})
        return trajectory

    def run(self, tasks: list[Task]) -> int:
        done = self.completed()
        started = time.monotonic()
        remaining = [t for t in tasks if t.id not in done]
        self._log({"event": "run_started", "agent": self.agent.name, "tasks": len(remaining)})
        for index, task in enumerate(remaining, 1):
            if self.total_timeout is not None:
                elapsed = time.monotonic() - started
                remaining_budget = self.total_timeout - elapsed
                if remaining_budget <= 0:
                    self._log({"event": "run_timeout", "completed_this_run": index - 1})
                    return 2
                timeout = min(self.task_timeout, remaining_budget)
            else:
                timeout = self.task_timeout
            print(f"[{index}/{len(remaining)}] {task.id} ...", flush=True)
            trajectory = self.run_task(task, timeout)
            print(f"    {'PASS' if trajectory.success else 'FAIL'}  {trajectory.duration_seconds:.1f}s", flush=True)
            if self.total_timeout is not None and time.monotonic() - started >= self.total_timeout:
                self._log({"event": "run_timeout", "completed_this_run": index})
                return 2
        self._log({"event": "run_finished", "tasks": len(remaining)})
        return 0
