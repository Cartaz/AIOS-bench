from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .failures import classify_failure
from .materialization import TaskMaterializer
from .models import Task
from .runner import BenchmarkRunner
from .server_metrics import build_server_metrics_client
from .task_execution import run_frontier_task


@dataclass(frozen=True)
class SuiteDefinition:
    name: str
    catalog_dir: str
    materializer: TaskMaterializer
    fixture_dirs: tuple[str, ...] = ()
    semantic_files: tuple[str, ...] = ()
    semantic_dirs: tuple[str, ...] = ()
    parametric: dict[str, Any] | None = None


BASE_SEMANTIC_FILES = (
    "adapters.py",
    "agentzero_client.py",
    "agentzero_workspace.py",
    "evaluators.py",
    "experiments.py",
    "failures.py",
    "fixtures.py",
    "frontier_runner.py",
    "goose_telemetry.py",
    "hermes_telemetry.py",
    "letta_telemetry.py",
    "manifest.py",
    "materialization.py",
    "models.py",
    "pi_rpc.py",
    "processes.py",
    "runner.py",
    "sandbox.py",
    "scheduler.py",
    "scoring.py",
    "task_execution.py",
    "tasks.py",
    "telemetry.py",
)
BASE_SEMANTIC_DIRS = ("server_metrics",)


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
    ) -> None:
        self.suite = suite
        self.server_metrics = build_server_metrics_client(server_metrics_url, model=server_metrics_model)
        self.server_metrics_model = server_metrics_model
        self.max_output_tokens = max_output_tokens
        self.metrics_poll_interval = metrics_poll_interval
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
        return {
            "cleanup": cleanup,
            "counts": counts,
            "latest": self._latest_results(),
        }

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
        return manifest

    def _landscape_execution_fingerprint(self) -> str:
        profile_manifest = json.loads(json.dumps(self.execution_manifest))
        parametric = profile_manifest.get("parametric")
        if isinstance(parametric, dict):
            parametric.pop("pressure_coordinates", None)
            parametric["pressure_coordinates_excluded_from_profile"] = True
        return hashlib.sha256(
            json.dumps(
                profile_manifest,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

    def _current_suite_revision(self) -> str:
        return self._revision()

    def _revision(self) -> str:
        digest = hashlib.sha256()
        roots = [self.repo_root / "benchmarks" / "tasks" / self.suite.catalog_dir]
        roots.extend(self.repo_root / path for path in self.suite.fixture_dirs)
        self._hash_files(digest, roots)

        benchmark_root = self.repo_root / "core" / "benchmark"
        for path in sorted(benchmark_root.glob("reference_checks*.py")):
            self._hash_path(digest, path)

        semantic_files = tuple(dict.fromkeys((*BASE_SEMANTIC_FILES, *self.suite.semantic_files)))
        for name in semantic_files:
            self._hash_path(digest, benchmark_root / name)

        semantic_dirs = tuple(dict.fromkeys((*BASE_SEMANTIC_DIRS, *self.suite.semantic_dirs)))
        for directory in semantic_dirs:
            self._hash_files(digest, [benchmark_root / directory], suffix=".py")
        return digest.hexdigest()

    def _catalog_task_count(self) -> list[str]:
        task_ids: list[str] = []
        catalog = self.repo_root / "benchmarks" / "tasks" / self.suite.catalog_dir
        for path in sorted(catalog.glob("*.json")):
            task_ids.extend(str(item["id"]) for item in json.loads(path.read_text(encoding="utf-8")))
        return task_ids

    def _workspace(self, task: Task) -> Path:
        return self.suite.materializer.prepare(self, task)

    def _result_identity(self, task: Task) -> dict:
        identity = super()._result_identity(task)
        identity.update(self.suite.materializer.identity(self, task))
        if self.suite.parametric is not None:
            identity["landscape_execution_fingerprint"] = self.landscape_execution_fingerprint
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
            **self._result_identity(task),
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
        self._write_result(item)
        self._log({"event": f"task_{status}", "task_id": task.id, "failure_kind": failure_kind, **reason})

    def run_task(self, task: Task, timeout: float):
        trajectory = run_frontier_task(self, task, timeout)
        self.suite.materializer.after_task(self, task)
        return trajectory

    def _hash_files(
        self,
        digest,
        roots: Iterable[Path],
        *,
        suffix: str | None = None,
    ) -> None:
        for root in roots:
            for path in sorted(
                item
                for item in root.rglob("*")
                if item.is_file()
                and "__pycache__" not in item.parts
                and item.suffix != ".pyc"
                and (suffix is None or item.suffix == suffix)
            ):
                self._hash_path(digest, path)

    def _hash_path(self, digest, path: Path) -> None:
        digest.update(path.relative_to(self.repo_root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
