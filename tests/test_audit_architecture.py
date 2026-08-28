from __future__ import annotations

import ast
import inspect
from pathlib import Path

from core.benchmark import materialization, task_execution
from core.benchmark.tasks import load_tasks

ROOT = Path(__file__).resolve().parents[1]


def test_task_executor_uses_public_runner_surface() -> None:
    source = inspect.getsource(task_execution)
    assert "runner._workspace" not in source
    assert "runner._log" not in source
    assert "runner._write_result" not in source
    assert "runner._result_identity" not in source
    assert "prepare_workspace" in source
    assert "record_result" in source


def test_static_materializer_setup_is_catalog_driven() -> None:
    source = inspect.getsource(materialization.StaticTaskMaterializer._apply_task_setup)
    assert "long_horizon_001" not in source
    assert "learning_003" not in source
    assert "memory_004" not in source

    tasks = {task.id: task for task in load_tasks(ROOT / "benchmarks" / "tasks")}
    assert tasks["long_horizon_001"].setup == ("long_horizon_corpus",)
    assert tasks["learning_003"].setup == ("learning_regression",)
    assert tasks["memory_004"].setup == ("git_fixture",)


def test_frontend_accessibility_and_responsive_contract() -> None:
    css = (ROOT / "ui" / "web" / "app.css").read_text(encoding="utf-8")
    html = (ROOT / "ui" / "web" / "index.html").read_text(encoding="utf-8")
    assert ".toggle:focus-visible" in css
    assert ".task:focus-visible" in css
    assert "min-width:1000px" not in css.replace(" ", "")
    assert 'lang="it"' in html
    assert "border-radius: 22px" in css
    assert "border-radius: 999px" not in css


def test_ruff_enables_full_pyflakes_family() -> None:
    config = (ROOT / "ruff.toml").read_text(encoding="utf-8")
    assert '"F"' in config
    assert '"F63"' not in config


def test_reference_check_entrypoints_use_descriptive_typed_parameters() -> None:
    for path in sorted((ROOT / "core" / "benchmark").glob("reference_checks*.py")):
        source = path.read_text(encoding="utf-8")
        assert "from __future__ import annotations" in source
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in {"check", "check_task"}:
                continue
            names = [argument.arg for argument in node.args.args]
            assert all(len(name) > 1 for name in names), (path.name, node.name, names)
            assert all(argument.annotation is not None for argument in node.args.args), (
                path.name,
                node.name,
                names,
            )
            assert node.returns is not None, (path.name, node.name)
