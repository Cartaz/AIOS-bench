from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from .failures import classify_failure
from .interventions import ExecutionCondition
from .materialization import TaskMaterializer
from .models import Task
from .runner import BenchmarkRunner
from .server_metrics import build_server_metrics_client
from .task_execution import run_frontier_task
from .task_runtime import TaskRuntime


@dataclass(frozen=True)
class SuiteDefinition:
    name: str
    catalog_dir: str
    materializer: TaskMaterializer
    fixture_dirs: tuple[str, ...] = ()
    parametric: dict[str, Any] | None = None


NON_SEMANTIC_MODULES = frozenset({
    "cli.py",
    "config.py",
    "dashboard.py",
    "doctor.py",
    "frontier_v3_runner.py",
    "frontier_v4_runner.py",
    "paths.py",
    "publication.py",
    "report.py",
    "smoke.py",
    "statistics.py",
    "validation.py",
})


def semantic_source_paths(repo_root: Path) -> tuple[Path, ...]:
    benchmark_root = repo_root / "core" / "benchmark"
    return tuple(
        path
        for path in sorted(benchmark_root.rglob("*.py"))
        if "__pycache__" not in path.parts and path.name not in NON_SEMANTIC_MODULES
    )


def _manifest_fingerprint(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


class FrontierRunner(BenchmarkRunner):
    """Single execution engine for static and generated Frontier suite catalogs."""

    def __init__(
        self,
        repo_root: Path,
        agent,
        results_dir: Path,
        task_timeout: float,
        total_timeout: float | None,
        *,
        suite: SuiteDefinition,
        resume: bool = True,
        model: str = "unknown",
        keep_raw: bool = False,
        run_id: str | None = None,
        server_metrics_url: str | None = None,
        server_metrics_model: str | None = None,
        max_output_tokens: int = 65536,
        metrics_poll_interval: float = 1.0,
        cancellation_check: Callable[[], bool] | None = None,
        execution_condition: ExecutionCondition | None = None,
    ) -> None:
        self.suite = suite
        self.execution_condition = execution_condition
        self.server_metrics = build_server_metrics_client(server_metrics_url, model=server_metrics_model)
        self.server_metrics_model = server_metrics_model
        self.max_output_tokens = max_output_tokens
        self.metrics_poll_interval = metrics_poll_interval
        self.cancellation_check = cancellation_check
        if run_id is None:
            run_id = (
                datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S_%f")
                + f"_{suite.name.replace('_', '-')}"
            )
        super().__init__(
            repo_root,
            agent,
            results_dir,
            task_timeout,
            total_timeout,
            resume=resume,
            model=model,
            keep_raw=keep_raw,
            run_id=run_id,
        )
        self.landscape_execution_fingerprint = self._landscape_execution_fingerprint()
        self.ablation_execution_fingerprint = self._ablation_execution_fingerprint()

    def latest_results(self) -> dict[str, dict]:
        return self._latest_results()

    def record_unsupported(self, task: Task, assessment) -> None:
        self._write_unsupported(task, assessment)

    def record_noncomparable(self, task: Task, status: str, reason: dict, assessment=None) -> None:
        self._write_noncomparable(task, status, reason, assessment)

    def finalize(self, tasks: list[Task], *, status: str, finished_at: str) -> dict[str, Any]:
        cleanup = self.cleanup()
        counts = self._run_counts(tasks)
        self._write_metadata(finished_at, status=status, counts=counts)
        if status == "completed":
            self._update_latest_pointer()
        else:
            self._clear_latest_if_current()
        return {"cleanup": cleanup, "counts": counts, "latest": self._latest_results()}

    def _suite_name(self) -> str:
        return self.suite.name

    def _execution_manifest(self) -> dict:
        manifest = super()._execution_manifest()
        manifest["server_metrics"] = {
            "source": self.server_metrics.source,
            "enabled": bool(self.server_metrics.enabled),
            "endpoint": self.server_metrics.public_endpoint,
            "model_filter": self.server_metrics_model,
            "output_token_cap": self.max_output_tokens,
            "poll_interval_seconds": self.metrics_poll_interval,
            "scope": "endpoint_aggregate",
            "requires_exclusive_server": True,
        }
        if self.suite.parametric is not None:
            manifest["parametric"] = self.suite.parametric
        if self.execution_condition is not None:
            manifest["intervention"] = self.execution_condition.manifest()
        return manifest

    def _landscape_execution_fingerprint(self) -> str:
        profile_manifest = json.loads(json.dumps(self.execution_manifest))
        parametric = profile_manifest.get("parametric")
        if isinstance(parametric, dict):
            parametric.pop("pressure_coordinates", None)
            parametric["pressure_coordinates_excluded_from_profile"] = True
        return _manifest_fingerprint(profile_manifest)

    def _ablation_execution_fingerprint(self) -> str:
        """Fingerprint the execution profile while excluding only skill arm choice."""
        profile_manifest = json.loads(json.dumps(self.execution_manifest))
        intervention = profile_manifest.get("intervention")
        if isinstance(intervention, dict) and "skill_mode" in intervention:
            intervention["skill_mode"] = "__paired_skill_variable__"
        return _manifest_fingerprint(profile_manifest)

    def _current_suite_revision(self) -> str:
        return self._revision()

    def _revision(self) -> str:
        digest = hashlib.sha256()
        roots = [self.repo_root / "benchmarks" / "tasks" / self.suite.catalog_dir]
        roots.extend(self.repo_root / path for path in self.suite.fixture_dirs)
        self._hash_files(digest, roots)
        for path in semantic_source_paths(self.repo_root):
            self._hash_path(digest, path)
        return digest.hexdigest()

    def _catalog_task_count(self) -> list[str]:
        task_ids: list[str] = []
        catalog = self.repo_root / "benchmarks" / "tasks" / self.suite.catalog_dir
        for path in sorted(catalog.glob("*.json")):
            task_ids.extend(
                str(item["id"])
                for item in json.loads(path.read_text(encoding="utf-8"))
            )
        return task_ids

    def prepare_workspace(self, task: Task) -> Path:
        """Materialize the isolated workspace for one task."""
        return self.suite.materializer.prepare(self, task)

    def start_task_runtime(self, task: Task, workspace: Path) -> TaskRuntime:
        """Start benchmark-owned services required only while a task executes."""
        return self.suite.materializer.start_runtime(self, task, workspace)

    def build_task_prompt(self, task: Task) -> str:
        prompt = (
            "You are being evaluated by AIOS-bench. Work only inside the provided workspace. "
            "Complete the task fully, verify the result, and do not modify benchmark files outside "
            "the workspace.\n\nTASK:\n" + task.prompt
        )
        if self.execution_condition is not None:
            prompt = self.execution_condition.augment_prompt(task, prompt)
        return prompt

    def _workspace(self, task: Task) -> Path:
        """Compatibility alias for existing tests/internal consumers."""
        return self.prepare_workspace(task)

    def result_identity(self, task: Task) -> dict:
        identity = super().result_identity(task)
        identity.update(self.suite.materializer.identity(self, task))
        if self.suite.parametric is not None:
            identity["landscape_execution_fingerprint"] = self.landscape_execution_fingerprint
        if self.execution_condition is not None:
            identity.update(self.execution_condition.task_identity(task))
            identity["ablation_execution_fingerprint"] = self.ablation_execution_fingerprint
        return identity

    def _write_noncomparable(self, task: Task, status: str, reason: dict, assessment=None) -> None:
        failure_kind = classify_failure(
            status=status,
            success=False,
            execution_success=False,
            evaluation_passed=None,
            events=(),
        )
        item = {
            **self.result_identity(task),
            "agent": self.agent.name,
            "success": False,
            "status": status,
            "failure_kind": failure_kind,
            "score": None,
            "comparable": False,
            "duration_seconds": 0.0,
            "reason": reason,
            "telemetry_available": False,
            "events": [],
            "evaluation": None,
            "usage_source": "unavailable",
            "efficiency_comparable": False,
            "server_usage": None,
        }
        if assessment is not None:
            item["capability_assessment"] = assessment.to_dict()
        self.record_result(item)
        self.record_event({
            "event": f"task_{status}",
            "task_id": task.id,
            "failure_kind": failure_kind,
            **reason,
        })

    def run_task(self, task: Task, timeout: float):
        trajectory = run_frontier_task(self, task, timeout)
        self.suite.materializer.after_task(self, task)
        return trajectory

    def _hash_files(self, digest, roots: Iterable[Path]) -> None:
        for root in roots:
            for path in sorted(
                item
                for item in root.rglob("*")
                if item.is_file()
                and "__pycache__" not in item.parts
                and item.suffix != ".pyc"
            ):
                self._hash_path(digest, path)

    def _hash_path(self, digest, path: Path) -> None:
        digest.update(path.relative_to(self.repo_root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
