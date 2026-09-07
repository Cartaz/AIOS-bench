from __future__ import annotations

import json
from pathlib import Path

from aios_bench.parametric import evaluate_variant, materialize_variant


def _write_wrong_expense_tool(workspace: Path) -> None:
    tool = workspace / "tools" / "expense_report.py"
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_text(
        "from __future__ import annotations\n"
        "import argparse\n"
        "from pathlib import Path\n\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--input', required=True)\n"
        "parser.add_argument('--output', required=True)\n"
        "args = parser.parse_args()\n"
        "Path(args.output).write_text('# incomplete report\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (workspace / "reports" / "monthly_expense_report.md").write_text(
        "# incomplete report\n",
        encoding="utf-8",
    )


def test_expense_failure_receives_deterministic_partial_credit(tmp_path):
    oracle = materialize_variant("expense_report", tmp_path, seed=41, parameters={})
    _write_wrong_expense_tool(tmp_path)

    grade = evaluate_variant("expense_report", tmp_path, oracle)

    assert grade.passed is False
    assert 0.0 < grade.score < 1.0
    assert grade.metrics["protected_integrity"] == 1.0
    assert grade.metrics["fixture_independence"] == 1.0


def test_config_failure_is_graded_by_existing_atomic_requirements(tmp_path):
    oracle = materialize_variant("config_traversal", tmp_path, seed=42, parameters={})
    first_key, first_value = next(iter(oracle["settings"].items()))
    report = tmp_path / "reports" / "effective_config.md"
    report.write_text(
        f"# Effective config\n\n{first_key}: {first_value}\n",
        encoding="utf-8",
    )

    grade = evaluate_variant("config_traversal", tmp_path, oracle)

    assert grade.passed is False
    assert 0.0 < grade.score < 1.0
    assert 0.0 < grade.metrics["settings_accuracy"] < 1.0


def test_config_strict_pass_semantics_are_unchanged(tmp_path):
    oracle = materialize_variant("config_traversal", tmp_path, seed=43, parameters={})
    lines = ["# Effective config", ""]
    lines.extend(f"{key}: {value}" for key, value in oracle["settings"].items())
    lines.append("")
    lines.extend(str(value) for value in oracle["reference_chain"])
    lines.append(str(oracle["consumer_path"]))
    (tmp_path / "reports" / "effective_config.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    grade = evaluate_variant("config_traversal", tmp_path, oracle)

    assert grade.passed is True
    assert grade.score == 1.0


def test_workspace_lineage_failure_receives_partial_credit(tmp_path):
    oracle = materialize_variant("workspace_lineage", tmp_path, seed=44, parameters={})
    report = {
        "active_release": oracle["active_release"],
        "root": oracle["root"],
        "lineage_paths": [],
        "effective_settings": {},
        "consumer_path": oracle["consumer_path"],
        "ignored_stale_sources": [],
    }
    (tmp_path / "reports" / "workspace_lineage.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )

    grade = evaluate_variant("workspace_lineage", tmp_path, oracle)

    assert grade.passed is False
    assert 0.0 < grade.score < 1.0
    assert grade.metrics["release_identity"] == 1.0
    assert grade.metrics["effective_settings_accuracy"] == 0.0


def test_stateful_world_failure_is_no_longer_binary(tmp_path):
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("stateful_world", workspace, seed=45, parameters={})

    grade = evaluate_variant(
        "stateful_world",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id="stateful_support_001",
    )

    assert grade.passed is False
    assert 0.0 < grade.score < 1.0
    assert grade.metrics["non_target_preservation"] == 1.0
    assert grade.metrics["target_mutation_accuracy"] == 0.0


def test_dependency_world_failure_is_no_longer_binary(tmp_path):
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("dependency_world", workspace, seed=46, parameters={})

    grade = evaluate_variant(
        "dependency_world",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id="support_dependency_001",
    )

    assert grade.passed is False
    assert 0.0 < grade.score < 1.0
    assert grade.metrics["account_preservation"] == 1.0
    assert grade.metrics["target_mutation_accuracy"] == 0.0


def test_tool_recovery_failure_is_no_longer_binary(tmp_path):
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("tool_recovery", workspace, seed=47, parameters={})

    grade = evaluate_variant(
        "tool_recovery",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id="tool_recovery_001",
    )

    assert grade.passed is False
    assert 0.0 < grade.score < 1.0
    assert grade.metrics["non_target_preservation"] == 1.0
    assert grade.metrics["target_process_accuracy"] == 0.0
