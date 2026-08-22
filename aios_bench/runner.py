from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .adapters import ADAPTERS, Adapter, PiAgentAdapter
from .evaluators import evaluate_artifacts
from .models import Task, Trajectory
from .manifest import build_run_manifest
from .pi_rpc import PiRPCClient
from .retention import prune_run_artifacts
from .scoring import overall_score
from .sandbox import workspace_sandbox
from .telemetry import parse_output


@dataclass(frozen=True)
class AgentConfig:
    name: str
    display_name: str
    adapter: Adapter


AGENTS = {
    name: AgentConfig(name, {
        "hermes": "Hermes Agent", "piagent": "Pi Agent", "opencode": "OpenCode",
        "goose": "Goose", "letta": "Letta", "agentzero": "Agent Zero",
        "claude": "Claude Code",
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


def _git_is_dirty(repo_root: Path) -> bool | None:
    try:
        output = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=repo_root, text=True, stderr=subprocess.DEVNULL,
        )
        return bool(output.strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def _suite_revision(repo_root: Path) -> str:
    catalog = repo_root / "benchmarks" / "tasks" / "frontier_v2.json"
    return hashlib.sha256(catalog.read_bytes()).hexdigest()


SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _safe_run_id(value: str) -> str:
    cleaned = value.strip()
    if not SAFE_RUN_ID.fullmatch(cleaned) or cleaned in {".", ".."}:
        raise ValueError("run_id must contain only letters, numbers, '.', '_' or '-'")
    return cleaned


def _model_path_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._") or "unknown"
    if cleaned == value and cleaned not in {".", ".."} and len(cleaned) <= 80:
        return cleaned
    suffix = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[:80]}-{suffix}"


def _write_json_atomic(path: Path, value: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


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
        self.model_dir = results_dir / agent.name / _model_path_component(model)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        if run_id is None:
            timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S_%f")
            run_id = f"{timestamp}_frontier-v2"
        self.run_id = _safe_run_id(run_id)
        self.run_dir = self.model_dir / "runs" / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint = self.run_dir / "results.jsonl"
        self.events = self.run_dir / "events.jsonl"
        self.metadata_path = self.run_dir / "run.json"
        self.suite_revision = self._current_suite_revision()
        self.git_commit = _git_commit(self.repo_root)
        self.git_dirty = _git_is_dirty(self.repo_root)
        self.execution_manifest = self._execution_manifest()
        self.execution_fingerprint = hashlib.sha256(
            json.dumps(self.execution_manifest, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        self._validate_existing_run()
        self._write_metadata(status="running")
        self._clear_latest_if_current()

    def _suite_name(self) -> str:
        return "frontier_v2"

    def _execution_manifest(self) -> dict:
        invocation = self.agent.adapter.build("", self.run_dir, self.model)
        sandbox = workspace_sandbox(self.agent.name, self.run_dir)
        custom_command = os.environ.get(f"AIOS_BENCH_{self.agent.name.upper()}_COMMAND")
        return build_run_manifest(self.agent.adapter, invocation, configuration={
            "runner_workspace_isolation": sandbox.strategy,
            "runner_write_confined": sandbox.write_confined,
            "runner_grader_hidden": sandbox.grader_hidden,
            "remote_project_boundary": self.agent.name == "agentzero",
            "task_timeout_seconds": self.task_timeout,
            "total_timeout_seconds": self.total_timeout,
            "custom_command_configured": bool(custom_command),
            "custom_command_sha256": (
                hashlib.sha256(custom_command.encode("utf-8")).hexdigest() if custom_command else None
            ),
            "retention_keep_raw": self.keep_raw,
        })

    def _validate_existing_run(self) -> None:
        if not self.metadata_path.exists():
            return
        try:
            existing = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid existing run metadata: {self.metadata_path}") from exc
        identity = {
            "suite": self._suite_name(), "suite_revision": self.suite_revision,
            "harness": self.agent.name, "model": self.model,
            "execution_fingerprint": self.execution_fingerprint,
        }
        mismatches = [key for key, value in identity.items() if existing.get(key) not in {None, value}]
        if mismatches:
            raise ValueError(f"run_id {self.run_id!r} belongs to incompatible metadata: {', '.join(mismatches)}")
        if not self.resume and self.checkpoint.exists() and self.checkpoint.stat().st_size:
            raise FileExistsError(f"run_id {self.run_id!r} already contains results; choose a new run id")

    def _write_metadata(self, finished_at: str | None = None, *, status: str | None = None,
                        counts: dict[str, int] | None = None) -> None:
        existing: dict = {}
        if self.metadata_path.exists():
            try:
                existing = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        manifest = existing.get("manifest") or existing.get("execution") or self.execution_manifest
        metadata = {
            "benchmark": "AIOS-bench",
            "suite": self._suite_name(),
            "suite_revision": self.suite_revision,
            "harness": self.agent.name,
            "model": self.model,
            "model_id": self.model,
            "run_id": self.run_id,
            "started_at": existing.get("started_at", _utc_now()),
            "git_commit": self.git_commit,
            "git_dirty": self.git_dirty,
            "task_count": len(self._catalog_task_count()),
            "status": status or existing.get("status", "running"),
            "manifest": manifest,
            "execution_fingerprint": self.execution_fingerprint,
        }
        metadata.update(counts or {})
        if finished_at is not None:
            metadata["finished_at"] = finished_at
        elif status != "running" and existing.get("finished_at"):
            metadata["finished_at"] = existing["finished_at"]
        _write_json_atomic(self.metadata_path, metadata)

    def _catalog_task_count(self) -> list[str]:
        catalog = self.repo_root / "benchmarks" / "tasks" / "frontier_v2.json"
        return [str(item["id"]) for item in json.loads(catalog.read_text(encoding="utf-8"))]

    def _update_latest_pointer(self) -> None:
        latest = self.model_dir / "latest"
        fallback = self.model_dir / "latest.txt"
        temporary_text = self.model_dir / ".latest.txt.tmp"
        temporary_text.write_text(self.run_id + "\n", encoding="utf-8")
        temporary_text.replace(fallback)
        try:
            temporary = self.model_dir / ".latest.tmp"
            temporary.unlink(missing_ok=True)
            temporary.symlink_to(Path("runs") / self.run_id, target_is_directory=True)
            temporary.replace(latest)
        except OSError:
            pass

    def _clear_latest_if_current(self) -> None:
        latest = self.model_dir / "latest"
        try:
            if latest.is_symlink() and latest.resolve() == self.run_dir.resolve():
                latest.unlink()
        except OSError:
            pass
        fallback = self.model_dir / "latest.txt"
        try:
            if fallback.is_file() and fallback.read_text(encoding="utf-8").strip() == self.run_id:
                fallback.unlink()
        except OSError:
            pass

    def _latest_results(self) -> dict[str, dict]:
        latest: dict[str, dict] = {}
        if not self.checkpoint.is_file():
            return latest
        for line_number, line in enumerate(
            self.checkpoint.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                self._log({"event": "checkpoint_line_ignored", "line": line_number})
                continue
            if item.get("suite_revision") == self.suite_revision and item.get("task_id"):
                latest[str(item["task_id"])] = item
        return latest

    def completed(self, tasks: list[Task]) -> set[str]:
        if not self.resume or not self.checkpoint.exists():
            return set()
        revisions = {t.id: t.revision for t in tasks}
        return {
            task_id for task_id, item in self._latest_results().items()
            if item.get("status") in {"completed", "unsupported"}
            and revisions.get(task_id) == item.get("task_revision", 1)
        }

    def _current_suite_revision(self) -> str:
        return _suite_revision(self.repo_root)

    def _log(self, event: dict) -> None:
        with self.events.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": time.time(), "run_id": self.run_id, **event}, ensure_ascii=False) + "\n")

    def _write_result(self, item: dict) -> None:
        with self.checkpoint.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _result_identity(self, task: Task) -> dict:
        return {
            "model": self.model, "harness": self.agent.name, "task_id": task.id,
            "task_revision": task.revision, "category": task.category, "tier": task.tier,
            "mode": task.mode, "run_id": self.run_id, "suite": self._suite_name(),
            "suite_revision": self.suite_revision, "git_commit": self.git_commit,
            "git_dirty": self.git_dirty,
        }

    def _write_noncomparable(self, task: Task, status: str, reason: dict,
                             assessment=None) -> None:
        item = {
            **self._result_identity(task), "agent": self.agent.name, "success": False,
            "status": status, "score": None, "comparable": False,
            "duration_seconds": 0.0, "reason": reason,
            "telemetry_available": False, "events": [], "evaluation": None,
        }
        if assessment is not None:
            item["capability_assessment"] = assessment.to_dict()
        self._write_result(item)
        self._log({"event": f"task_{status}", "task_id": task.id, **reason})

    def _write_unsupported(self, task: Task, assessment) -> None:
        self._write_noncomparable(
            task, "unsupported", {"missing_capabilities": sorted(assessment.missing)}, assessment,
        )

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
        sandbox = workspace_sandbox(self.agent.name, workspace)
        command = sandbox.wrap(command)
        env = os.environ.copy()
        env.update(invocation.environment)
        env.update({
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
                result = PiRPCClient(self.model, workspace, timeout, environment=env, command=command).run(prompt)
                stdout_path.write_text(result.stdout, encoding="utf-8")
                stderr_path.write_text(result.stderr, encoding="utf-8")
                if result.timed_out:
                    status = "timeout"
                    trajectory.errors = 1
                    trajectory.events.append({"type": "error", "source": "runner", "data": {"message": "Pi RPC task timeout"}})
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
            trajectory.events.append({"type": "error", "source": "runner", "data": {"kind": "agent_not_found", "error": str(exc)}})
        except Exception as exc:
            status = "error"
            trajectory.errors = 1
            trajectory.events.append({"type": "error", "source": "runner", "data": {"kind": "runner_error", "error": repr(exc)}})
        trajectory.duration_seconds = time.monotonic() - started

        stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
        runner_events = list(trajectory.events)
        parsed_events = [e.to_dict() for e in parse_output(stdout, stderr, source=self.agent.name)]
        trajectory.apply_events([*runner_events, *parsed_events])
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
                fixture_root=self.repo_root / "benchmarks" / "fixtures" / "workspace",
            )
            trajectory.evaluation_score = float(evaluation["acceptance_score"])
            trajectory.success = trajectory.success and bool(evaluation["passed"])
            if not trajectory.success and status == "completed":
                status = "failed"
            trajectory.events.append({"type": "deterministic_evaluation", "result": evaluation})

        result = trajectory.to_dict()
        result.update({
            "status": status, "evaluation": evaluation, "score": overall_score(trajectory),
            **self._result_identity(task), "comparable": True,
            "capability_assessment": self.agent.adapter.assess_task(task).to_dict(),
            "stdout": str(stdout_path), "stderr": str(stderr_path),
        })
        self._write_result(result)
        self._log({"event": "task_finished", "task_id": task.id, "success": trajectory.success,
                   "status": status, "duration": trajectory.duration_seconds, "score": result["score"],
                   "telemetry_available": trajectory.telemetry_available, "tier": task.tier})
        return trajectory

    def cleanup(self) -> dict[str, int | bool]:
        return prune_run_artifacts(self.run_dir, keep_raw=self.keep_raw)

    def _run_counts(self, tasks: list[Task]) -> dict[str, int]:
        latest = self._latest_results()
        supported = [task for task in tasks if self.agent.adapter.assess_task(task).is_supported]
        unsupported = len(tasks) - len(supported)
        attempted = [
            latest[task.id] for task in supported
            if task.id in latest and latest[task.id].get("status") != "blocked"
        ]
        return {
            "supported_task_count": len(supported),
            "unsupported_task_count": unsupported,
            "completed_task_count": len(latest),
            "attempted_task_count": len(attempted),
            "passed_task_count": sum(bool(item.get("success")) for item in attempted),
            "blocked_task_count": sum(item.get("status") == "blocked" for item in latest.values()),
        }

    def abort(self, tasks: list[Task]) -> None:
        try:
            self.cleanup()
        finally:
            self._write_metadata(_utc_now(), status="aborted", counts=self._run_counts(tasks))
            self._clear_latest_if_current()

    def run(self, tasks: list[Task]) -> int:
        done = self.completed(tasks)
        started = time.monotonic()
        remaining = [t for t in tasks if t.id not in done]
        print(f"AIOS-bench | {self.agent.display_name} | model={self.model} | run={self.run_id}")
        print(f"Tasks: {len(remaining)} (resume={'on' if self.resume else 'off'})")
        for index, task in enumerate(remaining, 1):
            assessment = self.agent.adapter.assess_task(task)
            if not assessment.is_supported:
                print(f"[{index}/{len(remaining)}] {task.id} [T{task.tier}] ... UNSUPPORTED "
                      f"({', '.join(sorted(assessment.missing))})", flush=True)
                self._write_unsupported(task, assessment)
                continue
            latest = self._latest_results()
            missing_dependencies = [
                dependency for dependency in task.depends_on
                if not latest.get(dependency, {}).get("success", False)
            ]
            if missing_dependencies:
                print(f"[{index}/{len(remaining)}] {task.id} [T{task.tier}] ... BLOCKED "
                      f"(dependencies: {', '.join(missing_dependencies)})", flush=True)
                self._write_noncomparable(
                    task, "blocked", {"missing_dependencies": missing_dependencies}, assessment,
                )
                continue
            timeout = self.task_timeout
            if self.total_timeout is not None:
                timeout = min(timeout, self.total_timeout - (time.monotonic() - started))
                if timeout <= 0:
                    self.cleanup()
                    self._write_metadata(_utc_now(), status="aborted", counts=self._run_counts(tasks))
                    return 2
            print(f"[{index}/{len(remaining)}] {task.id} [T{task.tier}] ...", flush=True)
            trajectory = self.run_task(task, timeout)
            score = overall_score(trajectory)
            print(f"    {'PASS' if trajectory.success else 'FAIL'}  {score:.1f}/100  {trajectory.duration_seconds:.1f}s", flush=True)
        cleanup = self.cleanup()
        counts = self._run_counts(tasks)
        latest = self._latest_results()
        comparable = [item for item in latest.values() if item.get("status") != "unsupported" and item.get("score") is not None]
        avg = sum(float(item["score"]) for item in comparable) / len(comparable) if comparable else 0.0
        self._write_metadata(_utc_now(), status="completed", counts=counts)
        self._update_latest_pointer()
        print(f"\nResult: {counts['passed_task_count']}/{counts['supported_task_count']} supported tasks passed"
              f" | unsupported={counts['unsupported_task_count']} | average score {avg:.1f}/100")
        if not self.keep_raw:
            print(f"Retention cleanup: removed {cleanup['files_removed']} files and {cleanup['dirs_removed']} dependency/cache directories")
        print(f"Results: {self.run_dir}")
        return 0 if counts["passed_task_count"] == counts["supported_task_count"] else 1
