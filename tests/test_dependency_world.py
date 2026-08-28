from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from aios_bench.parametric import (
    DependencyWorldPressure,
    check_variant,
    materialize_variant,
    start_variant_runtime,
)
from aios_bench.world_service import (
    SupportDependencyWorldService,
    world_action_log_path,
)


TASK_ID = "support_dependency_001"


def _visible_targets(
    workspace: Path,
    service: SupportDependencyWorldService,
) -> list[str]:
    policy = (workspace / "policies" / "current_escalation.md").read_text(
        encoding="utf-8"
    )
    plans_match = re.search(r"Eligible support plans: ([^.]+)\.", policy)
    severity_match = re.search(r"Severity threshold: (\d+)\.", policy)
    age_match = re.search(r"Age threshold hours: (\d+)\.", policy)
    assert plans_match and severity_match and age_match
    eligible_plans = {value.strip() for value in plans_match.group(1).split(",")}
    severity_threshold = int(severity_match.group(1))
    age_threshold = int(age_match.group(1))

    coverage_value = json.loads(
        (workspace / "routing" / "current_coverage.json").read_text(encoding="utf-8")
    )
    active = {
        (str(item["region"]), str(item["product"]))
        for item in coverage_value["active"]
    }

    targets: list[str] = []
    for ticket in service.list_tickets():
        account = service.get_account(str(ticket["account_id"]))
        qualifies = (
            ticket["status"] == "open"
            and (
                int(ticket["severity"]) >= severity_threshold
                or int(ticket["age_hours"]) >= age_threshold
            )
            and account["support_plan"] in eligible_plans
            and (str(account["region"]), str(ticket["product"])) in active
        )
        if qualifies:
            targets.append(str(ticket["id"]))
    return sorted(targets)


def _solve_visible(workspace: Path, oracle: dict, run_dir: Path) -> list[str]:
    service = SupportDependencyWorldService(
        workspace / oracle["database_path"],
        world_action_log_path(run_dir, TASK_ID),
    )
    targets = _visible_targets(workspace, service)
    for index, ticket_id in enumerate(targets, 1):
        service.escalate_ticket(ticket_id, f"visible-{index}-{ticket_id}")
    report = workspace / "reports" / "escalation_summary.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# Escalation summary\n\n"
        + "\n".join(f"- {ticket_id}" for ticket_id in targets)
        + "\n",
        encoding="utf-8",
    )
    return targets


def test_dependency_world_is_deterministic_and_pressure_sensitive(tmp_path: Path) -> None:
    pressure = DependencyWorldPressure(
        entity_count=36,
        account_count=15,
        required_mutations=6,
        distractor_policies=4,
        negative_constraints=8,
    )
    oracle_a = materialize_variant(
        "dependency_world",
        tmp_path / "a",
        seed=12345,
        parameters=pressure.to_dict(),
    )
    oracle_b = materialize_variant(
        "dependency_world",
        tmp_path / "b",
        seed=12345,
        parameters=pressure.to_dict(),
    )
    other_seed = materialize_variant(
        "dependency_world",
        tmp_path / "c",
        seed=12346,
        parameters=pressure.to_dict(),
    )
    other_pressure = materialize_variant(
        "dependency_world",
        tmp_path / "d",
        seed=12345,
        parameters={
            "entity_count": 40,
            "account_count": 18,
            "required_mutations": 6,
            "distractor_policies": 4,
            "negative_constraints": 8,
        },
    )

    assert oracle_a["variant_digest"] == oracle_b["variant_digest"]
    assert oracle_a["baseline_rows"] == oracle_b["baseline_rows"]
    assert oracle_a["baseline_accounts"] == oracle_b["baseline_accounts"]
    assert oracle_a["target_ids"] == oracle_b["target_ids"]
    assert oracle_a["variant_digest"] != other_seed["variant_digest"]
    assert oracle_a["variant_digest"] != other_pressure["variant_digest"]


def test_visible_information_chain_derives_exact_hidden_targets(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("dependency_world", workspace, seed=4242)
    service = SupportDependencyWorldService(
        workspace / oracle["database_path"],
        tmp_path / "reads.jsonl",
    )

    tickets = service.list_tickets()
    assert tickets
    assert all("support_plan" not in ticket and "region" not in ticket for ticket in tickets)
    assert "get_account" in oracle["mutation_interface"]["read_operations"]
    assert _visible_targets(workspace, service) == oracle["target_ids"]


def test_dependency_world_accepts_generic_visible_solution(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("dependency_world", workspace, seed=5000)

    untouched = check_variant(
        "dependency_world",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=TASK_ID,
    )
    assert untouched[0] is False

    targets = _solve_visible(workspace, oracle, run_dir)
    assert targets == oracle["target_ids"]
    assert check_variant(
        "dependency_world",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=TASK_ID,
    ) == (
        True,
        "support dependency world final state and information-chain constraints verified; "
        "world API action provenance verified",
    )


def test_dependency_world_rejects_direct_database_bypass(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("dependency_world", workspace, seed=5001)
    with sqlite3.connect(workspace / oracle["database_path"]) as connection:
        connection.executemany(
            """
            UPDATE tickets
            SET priority = 'urgent', assignee = 'oncall', escalation_reason = 'policy_match'
            WHERE id = ?
            """,
            [(ticket_id,) for ticket_id in oracle["target_ids"]],
        )
        connection.commit()
    report = workspace / "reports" / "escalation_summary.md"
    report.write_text("\n".join(oracle["target_ids"]) + "\n", encoding="utf-8")

    passed, detail = check_variant(
        "dependency_world",
        workspace,
        oracle,
        run_dir=run_dir,
        task_id=TASK_ID,
    )
    assert passed is False
    assert "world API action log" in detail


def test_dependency_world_rejects_account_and_source_side_effects(tmp_path: Path) -> None:
    account_workspace = tmp_path / "account"
    account_run = tmp_path / "account-run"
    account_oracle = materialize_variant(
        "dependency_world",
        account_workspace,
        seed=5002,
    )
    _solve_visible(account_workspace, account_oracle, account_run)
    with sqlite3.connect(account_workspace / account_oracle["database_path"]) as connection:
        connection.execute(
            "UPDATE accounts SET support_plan = 'basic' WHERE id = ?",
            (account_oracle["baseline_accounts"][0]["id"],),
        )
        connection.commit()
    passed, detail = check_variant(
        "dependency_world",
        account_workspace,
        account_oracle,
        run_dir=account_run,
        task_id=TASK_ID,
    )
    assert passed is False
    assert detail == "account state modified"

    source_workspace = tmp_path / "source"
    source_run = tmp_path / "source-run"
    source_oracle = materialize_variant(
        "dependency_world",
        source_workspace,
        seed=5003,
    )
    _solve_visible(source_workspace, source_oracle, source_run)
    coverage = source_workspace / "routing" / "current_coverage.json"
    coverage.write_text(
        coverage.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    passed, detail = check_variant(
        "dependency_world",
        source_workspace,
        source_oracle,
        run_dir=source_run,
        task_id=TASK_ID,
    )
    assert passed is False
    assert "protected source modified" in detail


def test_dependency_runtime_exposes_account_tool_and_hides_database(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("dependency_world", workspace, seed=5004)
    database = workspace / oracle["database_path"]

    runtime = start_variant_runtime(
        "dependency_world",
        workspace,
        run_dir=run_dir,
        task_id=TASK_ID,
        oracle=oracle,
    )
    try:
        assert not database.exists()
        env = os.environ.copy()
        env.update(runtime.environment)
        schema = subprocess.run(
            [sys.executable, "tools/world_api.py", "schema"],
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        assert "get_account" in json.loads(schema.stdout)["read_operations"]

        tickets = subprocess.run(
            [sys.executable, "tools/world_api.py", "list"],
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        ticket = json.loads(tickets.stdout)["tickets"][0]
        account = subprocess.run(
            [
                sys.executable,
                "tools/world_api.py",
                "account",
                ticket["account_id"],
            ],
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        account_value = json.loads(account.stdout)["account"]
        assert {"support_plan", "region"} <= set(account_value)
    finally:
        runtime.close()

    assert database.is_file()
    assert not (workspace / "world" / "api.json").exists()
