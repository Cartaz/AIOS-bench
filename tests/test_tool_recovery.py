from __future__ import annotations

import json
from pathlib import Path

import pytest

from aios_bench.evaluators import evaluate_artifacts
from aios_bench.failures import (
    RECOVERY_FAILURE,
    RETRY_LOOP,
    TOOL_SCHEMA_ERROR,
    TOOL_SELECTION_ERROR,
    classify_failure,
)
from aios_bench.parametric import (
    ToolRecoveryPressure,
    check_variant,
    materialize_variant,
)
from aios_bench.tool_recovery_api import start_tool_recovery_runtime
from aios_bench.tool_recovery_service import (
    ToolRecoveryError,
    ToolRecoveryService,
    diagnose_tool_recovery_failure,
    tool_action_log_path,
)
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"


def _task():
    return next(
        task
        for task in load_tasks(TASK_ROOT, "frontier_v4")
        if task.id == "tool_recovery_001"
    )


def _write_oracle(run_dir: Path, task_id: str, oracle: dict) -> None:
    path = run_dir / "oracles" / f"{task_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(oracle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _solve(workspace: Path, run_dir: Path, oracle: dict) -> None:
    service = ToolRecoveryService(
        workspace / oracle["state_path"],
        tool_action_log_path(run_dir, "tool_recovery_001"),
        oracle,
    )
    service.invoke("cases.list", {})
    for case_id in oracle["incomplete_case_ids"]:
        arguments = {"case_id": case_id}
        try:
            service.invoke("cases.get", arguments)
        except ToolRecoveryError as exc:
            assert exc.retryable is True
            service.invoke("cases.get", arguments)

    recovered: list[str] = []
    ambiguous = set(oracle["ambiguous_write_case_ids"])
    for index, case_id in enumerate(oracle["target_ids"], 1):
        arguments = {
            "case_id": case_id,
            "idempotency_key": f"test-{index}-{case_id}",
        }
        try:
            service.invoke("actions.process", arguments)
        except ToolRecoveryError as exc:
            assert exc.code == "response_lost"
            assert exc.retryable is True
            assert case_id in ambiguous
            service.invoke("actions.process", arguments)
            recovered.append(case_id)

    report = workspace / "reports" / "tool_recovery_summary.json"
    report.write_text(
        json.dumps(
            {
                "processed_case_ids": oracle["target_ids"],
                "recovered_case_ids": recovered,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_tool_recovery_variant_is_deterministic(tmp_path: Path) -> None:
    pressure = ToolRecoveryPressure(
        case_count=36,
        required_actions=7,
        distractor_tools=8,
        transient_failures=6,
        incomplete_responses=11,
    )
    first = materialize_variant(
        "tool_recovery",
        tmp_path / "first",
        seed=2026,
        parameters=pressure.to_dict(),
    )
    second = materialize_variant(
        "tool_recovery",
        tmp_path / "second",
        seed=2026,
        parameters=pressure.to_dict(),
    )

    assert first["variant_digest"] == second["variant_digest"]
    assert first["target_ids"] == second["target_ids"]
    assert first["transient_read_case_ids"] == second["transient_read_case_ids"]
    assert first["ambiguous_write_case_ids"] == second["ambiguous_write_case_ids"]


def test_tool_recovery_changes_with_seed_or_pressure(tmp_path: Path) -> None:
    baseline = materialize_variant("tool_recovery", tmp_path / "a", seed=7)
    other_seed = materialize_variant("tool_recovery", tmp_path / "b", seed=8)
    other_pressure = materialize_variant(
        "tool_recovery",
        tmp_path / "c",
        seed=7,
        parameters={
            "case_count": 32,
            "required_actions": 6,
            "distractor_tools": 6,
            "transient_failures": 5,
            "incomplete_responses": 10,
        },
    )

    assert baseline["variant_digest"] != other_seed["variant_digest"]
    assert baseline["variant_digest"] != other_pressure["variant_digest"]


def test_tool_recovery_happy_path_requires_transient_and_ambiguous_recovery(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("tool_recovery", workspace, seed=42)
    _solve(workspace, run_dir, oracle)

    passed, detail = check_variant(
        "tool_recovery",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id="tool_recovery_001",
    )

    assert oracle["transient_read_case_ids"]
    assert oracle["ambiguous_write_case_ids"]
    assert passed is True, detail


def test_tool_recovery_new_key_after_lost_response_is_not_idempotent(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("tool_recovery", workspace, seed=51)
    service = ToolRecoveryService(
        workspace / oracle["state_path"],
        tool_action_log_path(run_dir, "tool_recovery_001"),
        oracle,
    )
    case_id = oracle["ambiguous_write_case_ids"][0]
    with pytest.raises(ToolRecoveryError, match="response was lost"):
        service.invoke(
            "actions.process",
            {"case_id": case_id, "idempotency_key": "first-key"},
        )
    result = service.invoke(
        "actions.process",
        {"case_id": case_id, "idempotency_key": "second-key"},
    )

    assert result["process_count"] == 2
    assert diagnose_tool_recovery_failure(
        oracle,
        run_dir=run_dir,
        task_id="tool_recovery_001",
    ) == RECOVERY_FAILURE


def test_tool_recovery_diagnoses_tool_selection_and_schema_errors(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("tool_recovery", workspace, seed=61)
    service = ToolRecoveryService(
        workspace / oracle["state_path"],
        tool_action_log_path(run_dir, "tool_recovery_001"),
        oracle,
    )
    with pytest.raises(ToolRecoveryError):
        service.invoke(oracle["distractor_tool_names"][0], {"case_id": "CASE-0001"})
    assert diagnose_tool_recovery_failure(
        oracle,
        run_dir=run_dir,
        task_id="tool_recovery_001",
    ) == TOOL_SELECTION_ERROR

    second_workspace = tmp_path / "second"
    second_run = tmp_path / "second-run"
    second = materialize_variant("tool_recovery", second_workspace, seed=62)
    second_service = ToolRecoveryService(
        second_workspace / second["state_path"],
        tool_action_log_path(second_run, "tool_recovery_001"),
        second,
    )
    with pytest.raises(ToolRecoveryError):
        second_service.invoke("cases.get", {"case_id": "CASE-0001", "extra": True})
    assert diagnose_tool_recovery_failure(
        second,
        run_dir=second_run,
        task_id="tool_recovery_001",
    ) == TOOL_SCHEMA_ERROR


def test_tool_recovery_invalid_identifier_is_recorded_as_schema_error(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("tool_recovery", workspace, seed=63)
    service = ToolRecoveryService(
        workspace / oracle["state_path"],
        tool_action_log_path(run_dir, "tool_recovery_001"),
        oracle,
    )

    with pytest.raises(ToolRecoveryError):
        service.invoke("cases.get", {"case_id": "bad id with spaces"})

    assert diagnose_tool_recovery_failure(
        oracle,
        run_dir=run_dir,
        task_id="tool_recovery_001",
    ) == TOOL_SCHEMA_ERROR


def test_tool_recovery_detects_excessive_retry_after_retryable_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("tool_recovery", workspace, seed=64)
    service = ToolRecoveryService(
        workspace / oracle["state_path"],
        tool_action_log_path(run_dir, "tool_recovery_001"),
        oracle,
    )
    case_id = oracle["transient_read_case_ids"][0]

    with pytest.raises(ToolRecoveryError) as exc_info:
        service.invoke("cases.get", {"case_id": case_id})
    assert exc_info.value.retryable is True
    for _ in range(int(oracle["max_attempts_per_operation"])):
        service.invoke("cases.get", {"case_id": case_id})

    assert diagnose_tool_recovery_failure(
        oracle,
        run_dir=run_dir,
        task_id="tool_recovery_001",
    ) == RETRY_LOOP


def test_tool_recovery_evaluator_propagates_failure_kind(tmp_path: Path) -> None:
    task = _task()
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("tool_recovery", workspace, seed=71)
    _write_oracle(run_dir, task.id, oracle)
    service = ToolRecoveryService(
        workspace / oracle["state_path"],
        tool_action_log_path(run_dir, task.id),
        oracle,
    )
    with pytest.raises(ToolRecoveryError):
        service.invoke(oracle["distractor_tool_names"][0], {"case_id": "CASE-0001"})

    evaluation = evaluate_artifacts(
        workspace,
        list(task.acceptance),
        run_dir=run_dir,
        fixture_root=ROOT / "benchmarks" / "fixtures" / "workspace",
    )
    events = [{"type": "deterministic_evaluation", "result": evaluation}]

    assert evaluation["passed"] is False
    assert evaluation["failure_kind"] == TOOL_SELECTION_ERROR
    assert classify_failure(
        status="failed",
        success=False,
        execution_success=True,
        evaluation_passed=False,
        events=events,
    ) == TOOL_SELECTION_ERROR


def test_tool_recovery_runtime_hides_and_restores_operational_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("tool_recovery", workspace, seed=81)
    state_path = workspace / oracle["state_path"]
    assert state_path.is_file()

    runtime = start_tool_recovery_runtime(
        workspace,
        run_dir,
        "tool_recovery_001",
        oracle,
    )
    try:
        assert not state_path.exists()
        assert (workspace / "tool" / "api.json").is_file()
        assert runtime.environment["AIOS_BENCH_TOOL_API_URL"].startswith("http://127.0.0.1:")
    finally:
        runtime.close()

    assert state_path.is_file()
    assert not (workspace / "tool" / "api.json").exists()
