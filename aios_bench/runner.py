from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .evaluators import evaluate_artifacts
from .models import Task, Trajectory
from .scoring import overall_score


@dataclass(frozen=True)
class AgentConfig:
    name: str
    command: tuple[str, ...]
    display_name: str


AGENTS = {
    "hermes": AgentConfig("hermes", ("hermes", "chat", "-q"), "Hermes Agent"),
    "piagent": AgentConfig("piagent", ("pi", "-p"), "Pi Agent"),
    "opencode": AgentConfig("opencode", ("opencode",), "OpenCode"),
    "goose": AgentConfig("goose", ("goose",), "Goose"),
    "letta": AgentConfig("letta", ("letta",), "Letta"),
    "agentzero": AgentConfig("agentzero", ("agent-zero",), "Agent Zero"),
}


class BenchmarkRunner:
    def __init__(self, repo_root: Path, agent: AgentConfig, results_dir: Path,
                 task_timeout: float, total_timeout: float | None, resume: bool = True,
                 model: str = "unknown") -> None:
        self.repo_root = repo_root
        self.agent = agent
        self.results_dir = results_dir
        self.task_timeout = task_timeout
        self.total_timeout = total_timeout
        self.resume = resume
        self.model = model
        self.run_dir = results_dir / agent.name / model.replace("/", "_")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint = self.run_dir / "results.jsonl"
        self.events = self.run_dir / "events.jsonl"

    def completed(self) -> set[str]:
        if not self.resume or not self.checkpoint.exists():
            return set()
        done: set[str] = set()
        for line in self.checkpoint.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item.get("status") == "completed":
                    done.add(item["task_id"])
        return done

    def _log(self, event: dict) -> None:
        with self.events.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": time.time(), **event}, ensure_ascii=False) + "\n")

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
        command = [*self.agent.command, prompt]
        custom = os.environ.get(f"AIOS_BENCH_{self.agent.name.upper()}_COMMAND")
        if custom:
            import shlex
            command = [*shlex.split(custom), prompt]
        env = os.environ.copy()
        env.update({"AIOS_BENCH_TASK_ID": task.id, "AIOS_BENCH_WORKSPACE": str(workspace.resolve()),
                    "AIOS_BENCH_AGENT": self.agent.name, "AIOS_BENCH_MODEL": self.model})
        self._log({"event": "task_started", "task_id": task.id, "command": command, "model": self.model})
        started = time.monotonic()
        trajectory = Trajectory(agent=self.agent.name, task_id=task.id)
        status = "completed"
        try:
            with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
                proc = subprocess.run(command, cwd=workspace, env=env, stdout=out, stderr=err,
                                      text=True, timeout=timeout, check=False)
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
            spec_data = json.loads(spec.read_text(encoding="utf-8"))
            evaluation = evaluate_artifacts(workspace, spec_data["checks"])
            trajectory.success = trajectory.success and bool(evaluation["passed"])
            if not trajectory.success and status == "completed":
                status = "failed"
            trajectory.events.append({"type": "deterministic_evaluation", "result": evaluation})

        result = trajectory.to_dict()
        result.update({
            "status": status,
            "evaluation": evaluation,
            "score": overall_score(trajectory),
            "model": self.model,
            "harness": self.agent.name,
            "task_id": task.id,
            "category": task.category,
            "mode": task.mode,
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
        })
        self._write_result(result)
        self._log({"event": "task_finished", "task_id": task.id, "success": trajectory.success,
                   "status": status, "duration": trajectory.duration_seconds, "score": result["score"]})
        return trajectory

    def run(self, tasks: list[Task]) -> int:
        done = self.completed()
        started = time.monotonic()
        remaining = [t for t in tasks if t.id not in done]
        print(f"AIOS-bench | {self.agent.display_name} | model={self.model}")
        print(f"Tasks: {len(remaining)} (resume={'on' if self.resume else 'off'})")
        passed = 0
        scores: list[float] = []
        for index, task in enumerate(remaining, 1):
            timeout = self.task_timeout
            if self.total_timeout is not None:
                timeout = min(timeout, self.total_timeout - (time.monotonic() - started))
                if timeout <= 0:
                    return 2
            print(f"[{index}/{len(remaining)}] {task.id} ...", flush=True)
            trajectory = self.run_task(task, timeout)
            score = overall_score(trajectory)
            scores.append(score)
            if trajectory.success:
                passed += 1
            print(f"    {'PASS' if trajectory.success else 'FAIL'}  {score:.1f}/100  {trajectory.duration_seconds:.1f}s", flush=True)
        avg = sum(scores) / len(scores) if scores else 0.0
        print(f"\nResult: {passed}/{len(remaining)} passed | average score {avg:.1f}/100")
        print(f"Results: {self.run_dir}")
        return 0 if passed == len(remaining) else 1
