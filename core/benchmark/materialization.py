from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from .experiments import derive_seed
from .fixtures import materialize_long_horizon_corpus
from .models import Task
from .parametric import materialize_variant, persistent_state_paths, start_variant_runtime
from .task_runtime import TaskRuntime


class RunnerContext(Protocol):
    repo_root: Path
    run_dir: Path


class TaskMaterializer(Protocol):
    def prepare(self, runner: RunnerContext, task: Task) -> Path: ...

    def identity(self, runner: RunnerContext, task: Task) -> dict[str, Any]: ...

    def start_runtime(
        self,
        runner: RunnerContext,
        task: Task,
        workspace: Path,
    ) -> TaskRuntime: ...

    def after_task(self, runner: RunnerContext, task: Task) -> None: ...


def _fresh_workspace(run_dir: Path, task_id: str) -> Path:
    path = run_dir / "workspaces" / task_id
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


class StaticTaskMaterializer:
    """Materialize frozen Frontier v3 fixtures and their declarative setup steps."""

    _STATE_DIR = {"memory": ".agent_memory", "learning": "skills"}

    def prepare(self, runner: RunnerContext, task: Task) -> Path:
        path = _fresh_workspace(runner.run_dir, task.id)
        fixture_root = runner.repo_root / "benchmarks" / "fixtures" / "workspace"
        shutil.copytree(fixture_root, path, dirs_exist_ok=True)
        self._restore_warm_state(runner, task, path)
        self._apply_task_setup(task, path)
        return path

    def identity(self, runner: RunnerContext, task: Task) -> dict[str, Any]:
        return {}

    def start_runtime(
        self,
        runner: RunnerContext,
        task: Task,
        workspace: Path,
    ) -> TaskRuntime:
        return TaskRuntime()

    def after_task(self, runner: RunnerContext, task: Task) -> None:
        state_name = self._STATE_DIR.get(task.category)
        if state_name is None:
            return
        source = runner.run_dir / "workspaces" / task.id / state_name
        if not source.is_dir():
            return
        destination = self._state_root(runner, task.category) / state_name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)

    def _restore_warm_state(self, runner: RunnerContext, task: Task, workspace: Path) -> None:
        state_name = self._STATE_DIR.get(task.category)
        if state_name is None or task.mode != "warm":
            return
        source = self._state_root(runner, task.category) / state_name
        if not source.is_dir():
            return
        destination = workspace / state_name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)

    @staticmethod
    def _state_root(runner: RunnerContext, category: str) -> Path:
        path = runner.run_dir / "persistent_state" / category
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _apply_task_setup(self, task: Task, workspace: Path) -> None:
        handlers = {
            "long_horizon_corpus": self._setup_long_horizon,
            "learning_regression": self._setup_learning_regression,
            "git_fixture": self._setup_git_fixture,
        }
        for setup_name in task.setup:
            handler = handlers.get(setup_name)
            if handler is None:
                raise ValueError(f"Unknown static task setup: {setup_name}")
            handler(workspace)

    @staticmethod
    def _setup_long_horizon(workspace: Path) -> None:
        materialize_long_horizon_corpus(workspace)

    @staticmethod
    def _setup_learning_regression(workspace: Path) -> None:
        path = workspace / "skills" / "reporting_workflow.md"
        text = (
            path.read_text(encoding="utf-8")
            if path.is_file()
            else "# Reporting workflow\n"
        )
        text = text.replace(
            "Total revenue = sum of `revenue`",
            "Total revenue = sum of the `units` column",
        ).replace(
            "Total revenue = sum of revenue",
            "Total revenue = sum of the `units` column",
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    @staticmethod
    def _setup_git_fixture(workspace: Path) -> None:
        commands = (
            ("git", "init", "-q"),
            ("git", "config", "user.email", "bench@aios-bench.local"),
            ("git", "config", "user.name", "AIOS-bench"),
            ("git", "add", "-A"),
            ("git", "commit", "-qm", "fixture baseline"),
        )
        for command in commands:
            subprocess.run(command, cwd=workspace, check=True)


@dataclass
class ParametricTaskMaterializer:
    """Materialize deterministic variants and keep grader oracles outside workspaces.

    Families may declare benchmark-owned persistent paths. Cold tasks start with
    fresh state; predecessor work is persisted after execution and restored into
    later warm tasks in the same state scope.
    """

    base_seed: int = 42
    parameters: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    _variants: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)

    def prepare(self, runner: RunnerContext, task: Task) -> Path:
        workspace = _fresh_workspace(runner.run_dir, task.id)
        family = self.family(task)
        self._restore_persistent_state(runner, task, workspace, family)
        oracle = materialize_variant(
            family,
            workspace,
            seed=self.task_seed(task),
            parameters=self.parameters.get(family, {}),
            context=self.variant_context(task),
        )
        oracle_dir = runner.run_dir / "oracles"
        oracle_dir.mkdir(parents=True, exist_ok=True)
        oracle_path = oracle_dir / f"{task.id}.json"
        temporary = oracle_path.with_name(f".{oracle_path.name}.tmp")
        temporary.write_text(
            json.dumps(oracle, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(oracle_path)
        self._variants[task.id] = oracle
        return workspace

    def identity(self, runner: RunnerContext, task: Task) -> dict[str, Any]:
        family = self.family(task)
        variant = self._variants.get(task.id) or {}
        parameters = variant.get("parameters")
        if not isinstance(parameters, dict):
            parameters = dict(self.parameters.get(family, {}))
        identity = {
            "variant_schema": "aios-bench/parametric/v1",
            "variant_family": family,
            "variant_seed": self.task_seed(task),
            "variant_parameters": parameters,
            "variant_digest": variant.get("variant_digest"),
        }
        context = self.variant_context(task)
        if context:
            identity["variant_context"] = context
        return identity

    def start_runtime(
        self,
        runner: RunnerContext,
        task: Task,
        workspace: Path,
    ) -> TaskRuntime:
        oracle = self._variants.get(task.id)
        if oracle is None:
            raise RuntimeError(f"task variant was not prepared before runtime startup: {task.id}")
        return start_variant_runtime(
            self.family(task),
            workspace,
            run_dir=runner.run_dir,
            task_id=task.id,
            oracle=oracle,
        )

    def after_task(self, runner: RunnerContext, task: Task) -> None:
        family = self.family(task)
        paths = persistent_state_paths(family)
        if not paths:
            return
        workspace = runner.run_dir / "workspaces" / task.id
        state_root = self._state_root(runner, task, family)
        for relative in paths:
            self._persist_path(workspace, state_root, relative)

    @staticmethod
    def _reference(task: Task) -> Mapping[str, Any]:
        checks = [
            check
            for check in task.acceptance
            if check.get("type") == "parametric_reference"
        ]
        if len(checks) != 1:
            raise ValueError(
                f"Parametric task {task.id} needs exactly one parametric_reference"
            )
        return checks[0]

    @classmethod
    def family(cls, task: Task) -> str:
        return str(cls._reference(task)["family"])

    @classmethod
    def variant_context(cls, task: Task) -> dict[str, Any]:
        raw = cls._reference(task).get("variant_context", {})
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise ValueError(f"Parametric task {task.id} variant_context must be an object")
        return {str(key): value for key, value in raw.items()}

    def task_seed(self, task: Task) -> int:
        return derive_seed(self.base_seed, "task", task.id)

    def _restore_persistent_state(
        self,
        runner: RunnerContext,
        task: Task,
        workspace: Path,
        family: str,
    ) -> None:
        if task.mode != "warm":
            return
        paths = persistent_state_paths(family)
        if not paths:
            return
        state_root = self._state_root(runner, task, family)
        for relative in paths:
            self._restore_path(state_root, workspace, relative)

    def _state_root(
        self,
        runner: RunnerContext,
        task: Task,
        family: str,
    ) -> Path:
        context = self.variant_context(task)
        scope = str(context.get("state_scope", family))
        component = self._safe_component(scope)
        path = runner.run_dir / "persistent_state" / family / component
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _safe_component(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._")
        if cleaned and cleaned == value and cleaned not in {".", ".."} and len(cleaned) <= 80:
            return cleaned
        suffix = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
        return f"{(cleaned or 'state')[:64]}-{suffix}"

    @staticmethod
    def _relative_state_path(value: str) -> Path:
        path = Path(value)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError(f"Unsafe persistent state path: {value!r}")
        return path

    @classmethod
    def _restore_path(cls, state_root: Path, workspace: Path, relative: str) -> None:
        path = cls._relative_state_path(relative)
        source = state_root / path
        if not source.exists():
            return
        destination = workspace / path
        if destination.is_dir():
            shutil.rmtree(destination)
        elif destination.exists():
            destination.unlink()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)

    @classmethod
    def _persist_path(cls, workspace: Path, state_root: Path, relative: str) -> None:
        path = cls._relative_state_path(relative)
        source = workspace / path
        destination = state_root / path
        if destination.is_dir():
            shutil.rmtree(destination)
        elif destination.exists():
            destination.unlink()
        if not source.exists():
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
