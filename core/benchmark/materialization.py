from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from .experiments import derive_seed
from .fixtures import materialize_long_horizon_corpus
from .models import Task
from .parametric import materialize_variant


class RunnerContext(Protocol):
    repo_root: Path
    run_dir: Path


class TaskMaterializer(Protocol):
    def prepare(self, runner: RunnerContext, task: Task) -> Path: ...

    def identity(self, runner: RunnerContext, task: Task) -> dict[str, Any]: ...

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
    """Materialize deterministic variants and keep grader oracles outside workspaces."""

    base_seed: int = 42
    parameters: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    _variants: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)

    def prepare(self, runner: RunnerContext, task: Task) -> Path:
        workspace = _fresh_workspace(runner.run_dir, task.id)
        family = self.family(task)
        oracle = materialize_variant(
            family,
            workspace,
            seed=self.task_seed(task),
            parameters=self.parameters.get(family, {}),
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
        return {
            "variant_schema": "aios-bench/parametric/v1",
            "variant_family": family,
            "variant_seed": self.task_seed(task),
            "variant_parameters": parameters,
            "variant_digest": variant.get("variant_digest"),
        }

    def after_task(self, runner: RunnerContext, task: Task) -> None:
        return None

    @staticmethod
    def family(task: Task) -> str:
        checks = [
            check
            for check in task.acceptance
            if check.get("type") == "parametric_reference"
        ]
        if len(checks) != 1:
            raise ValueError(
                f"Parametric task {task.id} needs exactly one parametric_reference"
            )
        return str(checks[0]["family"])

    def task_seed(self, task: Task) -> int:
        return derive_seed(self.base_seed, "task", task.id)
