from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from core.benchmark.materialization import ParametricTaskMaterializer
from core.benchmark.parametric.tool_branching import (
    ToolBranchingPressure,
    check_tool_branching_variant,
    expected_resolution,
    generate_tool_branching_variant,
)


ROOT = Path(__file__).resolve().parents[1]


def _run_tool(workspace: Path, name: str, argument: str = "") -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(workspace / "tools" / f"{name}.py")]
    if argument:
        command.append(argument)
    return subprocess.run(command, cwd=workspace, text=True, capture_output=True, timeout=5, check=False)


def _materialized(tmp_path: Path):
    task = SimpleNamespace(
        id="tool-branch-test",
        acceptance=({"type": "parametric_reference", "family": "tool_branching"},),
    )
    runner = SimpleNamespace(repo_root=ROOT, run_dir=tmp_path / "run")
    materializer = ParametricTaskMaterializer(base_seed=47)
    workspace = materializer.prepare(runner, task)
    return materializer, runner, task, workspace, materializer._variants[task.id]


def test_tool_branching_generation_is_seeded_and_has_real_distractors(tmp_path: Path) -> None:
    first = generate_tool_branching_variant(
        tmp_path / "a",
        seed=91,
        pressure=ToolBranchingPressure(distractor_tools=4),
    )
    second = generate_tool_branching_variant(
        tmp_path / "b",
        seed=91,
        pressure=ToolBranchingPressure(distractor_tools=4),
    )

    assert first == second
    assert first["branch"] in {"billing", "access"}
    assert len(first["distractor_tools"]) == 4
    assert all((tmp_path / "a" / "tools" / f"{name}.py").is_file() for name in first["distractor_tools"])


def test_authoritative_inspection_then_branch_specific_lookup_produces_valid_resolution(tmp_path: Path) -> None:
    materializer, runner, task, workspace, oracle = _materialized(tmp_path)
    try:
        inspected = _run_tool(workspace, "inspect_case")
        assert inspected.returncode == 0, inspected.stderr
        inspection = json.loads(inspected.stdout)
        lookup_name = f"{inspection['case_type']}_lookup"
        looked_up = _run_tool(workspace, lookup_name, inspection["case_id"])
        assert looked_up.returncode == 0, looked_up.stderr
        lookup = json.loads(looked_up.stdout)

        report = workspace / "reports" / "case_resolution.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            json.dumps({
                "case_type": inspection["case_type"],
                "case_id": inspection["case_id"],
                "value": lookup["value"],
                "inspection_receipt": inspection["receipt"],
                "lookup_receipt": lookup["receipt"],
            }, sort_keys=True),
            encoding="utf-8",
        )
        passed, detail = check_tool_branching_variant(workspace, oracle)
        assert passed is True, detail
        assert json.loads(report.read_text(encoding="utf-8")) == expected_resolution(oracle)
    finally:
        materializer.after_task(runner, task)


def test_distractor_call_contaminates_session_and_blocks_authoritative_path(tmp_path: Path) -> None:
    materializer, runner, task, workspace, oracle = _materialized(tmp_path)
    try:
        distractor = str(oracle["distractor_tools"][0])
        bait = _run_tool(workspace, distractor)
        assert bait.returncode == 0
        inspected = _run_tool(workspace, "inspect_case")
        assert inspected.returncode == 2
        assert "contaminated" in inspected.stderr
    finally:
        materializer.after_task(runner, task)


def test_wrong_branch_or_wrong_case_id_is_rejected(tmp_path: Path) -> None:
    materializer, runner, task, workspace, _oracle = _materialized(tmp_path)
    try:
        inspected = _run_tool(workspace, "inspect_case")
        inspection = json.loads(inspected.stdout)
        wrong_branch = "access_lookup" if inspection["case_type"] == "billing" else "billing_lookup"
        wrong = _run_tool(workspace, wrong_branch, inspection["case_id"])
        assert wrong.returncode == 2
        assert "wrong branch" in wrong.stderr
    finally:
        materializer.after_task(runner, task)

    materializer, runner, task, workspace, _oracle = _materialized(tmp_path / "wrong-id")
    try:
        inspection = json.loads(_run_tool(workspace, "inspect_case").stdout)
        lookup_name = f"{inspection['case_type']}_lookup"
        wrong_id = _run_tool(workspace, lookup_name, "case-0000")
        assert wrong_id.returncode == 2
        assert "does not match" in wrong_id.stderr
    finally:
        materializer.after_task(runner, task)


def test_wrong_case_id_is_recoverable_without_contaminating_branch(tmp_path: Path) -> None:
    materializer, runner, task, workspace, oracle = _materialized(tmp_path)
    try:
        inspection = json.loads(_run_tool(workspace, "inspect_case").stdout)
        lookup_name = f"{inspection['case_type']}_lookup"
        wrong = _run_tool(workspace, lookup_name, "case-0000")
        assert wrong.returncode == 2
        corrected = _run_tool(workspace, lookup_name, inspection["case_id"])
        assert corrected.returncode == 0, corrected.stderr
        result = json.loads(corrected.stdout)
        assert result["value"] == str(oracle["expected_value"])
    finally:
        materializer.after_task(runner, task)
