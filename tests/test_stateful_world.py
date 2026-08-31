from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from aios_bench.parametric import (
    StatefulWorldPressure,
    check_variant,
    materialize_variant,
    start_variant_runtime,
)
from aios_bench.world_api import SupportWorldService, world_action_log_path


TASK_ID = "stateful_support_001"


def _solve(workspace: Path, oracle: dict, run_dir: Path) -> None:
    database = workspace / oracle["database_path"]
    service = SupportWorldService(database, world_action_log_path(run_dir, TASK_ID))
    target_ids = list(oracle["target_ids"])
    for index, ticket_id in enumerate(target_ids, 1):
        service.escalate_ticket(ticket_id, f"test-{index}-{ticket_id}")

    report = workspace / "reports" / "escalation_summary.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# Escalation summary\n\n" + "\n".join(f"- {ticket_id}" for ticket_id in target_ids) + "\n",
        encoding="utf-8",
    )


def test_stateful_world_is_deterministic_for_same_seed(tmp_path: Path) -> None:
    pressure = StatefulWorldPressure(
        entity_count=32,
        required_mutations=6,
        distractor_policies=4,
        negative_constraints=5,
    )
    oracle_a = materialize_variant(
        "stateful_world",
        tmp_path / "a",
        seed=12345,
        parameters=pressure.to_dict(),
    )
    oracle_b = materialize_variant(
        "stateful_world",
        tmp_path / "b",
        seed=12345,
        parameters=pressure.to_dict(),
    )

    assert oracle_a["variant_digest"] == oracle_b["variant_digest"]
    assert oracle_a["baseline_rows"] == oracle_b["baseline_rows"]
    assert oracle_a["protected_sha256"] == oracle_b["protected_sha256"]
    assert oracle_a["target_ids"] == oracle_b["target_ids"]
    assert (tmp_path / "a" / "tools" / "world_api.py").read_bytes() == (
        tmp_path / "b" / "tools" / "world_api.py"
    ).read_bytes()


def test_stateful_world_changes_with_seed_or_pressure(tmp_path: Path) -> None:
    baseline = materialize_variant("stateful_world", tmp_path / "a", seed=7)
    other_seed = materialize_variant("stateful_world", tmp_path / "b", seed=8)
    other_pressure = materialize_variant(
        "stateful_world",
        tmp_path / "c",
        seed=7,
        parameters={
            "entity_count": 30,
            "required_mutations": 4,
            "distractor_policies": 2,
            "negative_constraints": 5,
        },
    )

    assert baseline["variant_digest"] != other_seed["variant_digest"]
    assert baseline["variant_digest"] != other_pressure["variant_digest"]


def test_stateful_world_rejects_untouched_and_accepts_exact_api_final_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("stateful_world", workspace, seed=4242)

    untouched = check_variant(
        "stateful_world",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=TASK_ID,
    )
    assert untouched[0] is False

    _solve(workspace, oracle, run_dir)
    solved = check_variant(
        "stateful_world",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=TASK_ID,
    )
    assert solved == (
        True,
        "stateful support world final state and negative constraints verified; world API action provenance verified",
    )


def test_direct_database_solution_without_api_provenance_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("stateful_world", workspace, seed=4243)
    target_ids = list(oracle["target_ids"])
    with sqlite3.connect(workspace / oracle["database_path"]) as connection:
        connection.executemany(
            """
            UPDATE tickets
            SET priority = 'urgent', assignee = 'oncall', escalation_reason = 'policy_match'
            WHERE id = ?
            """,
            [(ticket_id,) for ticket_id in target_ids],
        )
        connection.commit()
    report = workspace / "reports" / "escalation_summary.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(target_ids) + "\n", encoding="utf-8")

    passed, detail = check_variant(
        "stateful_world",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=TASK_ID,
    )
    assert passed is False
    assert "world API action log" in detail


def test_stateful_world_rejects_non_target_side_effect(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("stateful_world", workspace, seed=31337)
    _solve(workspace, oracle, run_dir)

    target_ids = set(oracle["target_ids"])
    non_target = next(
        row["id"] for row in oracle["baseline_rows"] if row["id"] not in target_ids
    )
    with sqlite3.connect(workspace / oracle["database_path"]) as connection:
        connection.execute(
            "UPDATE tickets SET assignee = 'oncall' WHERE id = ?",
            (non_target,),
        )
        connection.commit()

    passed, detail = check_variant(
        "stateful_world",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=TASK_ID,
    )
    assert passed is False
    assert detail == f"non-target ticket modified: {non_target}"


def test_stateful_world_rejects_schema_and_policy_tampering(tmp_path: Path) -> None:
    schema_workspace = tmp_path / "schema"
    schema_run = tmp_path / "schema-run"
    schema_oracle = materialize_variant("stateful_world", schema_workspace, seed=100)
    _solve(schema_workspace, schema_oracle, schema_run)
    with sqlite3.connect(schema_workspace / schema_oracle["database_path"]) as connection:
        connection.execute("ALTER TABLE tickets ADD COLUMN unexpected TEXT")
        connection.commit()

    passed, detail = check_variant(
        "stateful_world",
        schema_workspace,
        schema_oracle,
        run_dir=schema_run,
        task_id=TASK_ID,
    )
    assert passed is False
    assert "database schema modified" in detail

    policy_workspace = tmp_path / "policy"
    policy_run = tmp_path / "policy-run"
    policy_oracle = materialize_variant("stateful_world", policy_workspace, seed=101)
    _solve(policy_workspace, policy_oracle, policy_run)
    policy = policy_workspace / "policies" / "current_escalation.md"
    policy.write_text(policy.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")

    passed, detail = check_variant(
        "stateful_world",
        policy_workspace,
        policy_oracle,
        run_dir=policy_run,
        task_id=TASK_ID,
    )
    assert passed is False
    assert "protected source modified" in detail


def test_runtime_hides_database_exposes_client_and_restores_final_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("stateful_world", workspace, seed=2026)
    database = workspace / oracle["database_path"]
    assert database.is_file()

    runtime = start_variant_runtime(
        "stateful_world",
        workspace,
        run_dir=run_dir,
        task_id=TASK_ID,
        oracle=oracle,
    )
    try:
        assert not database.exists()
        assert (workspace / "world" / "api.json").is_file()
        env = os.environ.copy()
        env.update(runtime.environment)
        target = oracle["target_ids"][0]
        command = [
            sys.executable,
            "tools/world_api.py",
            "escalate",
            target,
            "--idempotency-key",
            "runtime-test",
        ]
        first = subprocess.run(command, cwd=workspace, env=env, text=True, capture_output=True, check=True)
        second = subprocess.run(command, cwd=workspace, env=env, text=True, capture_output=True, check=True)
        assert json.loads(first.stdout)["changed"] is True
        assert json.loads(second.stdout)["idempotent_replay"] is True
    finally:
        runtime.close()

    assert database.is_file()
    assert not (workspace / "world" / "api.json").exists()
    records = [
        json.loads(line)
        for line in world_action_log_path(run_dir, TASK_ID).read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["ticket_id"] == oracle["target_ids"][0]
