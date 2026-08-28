from __future__ import annotations

import hashlib
import json
import random
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class DependencyWorldPressure:
    """Concrete workload coordinates for the support information-gap scenario."""

    entity_count: int = 30
    account_count: int = 12
    required_mutations: int = 5
    distractor_policies: int = 3
    negative_constraints: int = 6

    def __post_init__(self) -> None:
        if not 10 <= self.entity_count <= 500:
            raise ValueError("entity_count must be between 10 and 500")
        if not 4 <= self.account_count <= 200:
            raise ValueError("account_count must be between 4 and 200")
        if not 1 <= self.required_mutations <= min(64, self.entity_count // 2):
            raise ValueError(
                "required_mutations must be between 1 and min(64, entity_count//2)"
            )
        if not 0 <= self.distractor_policies <= 16:
            raise ValueError("distractor_policies must be between 0 and 16")
        if not 1 <= self.negative_constraints <= 64:
            raise ValueError("negative_constraints must be between 1 and 64")
        if self.required_mutations + self.negative_constraints > self.entity_count - 2:
            raise ValueError(
                "entity_count must leave at least two filler entities beyond "
                "targets and negative constraints"
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DependencyWorldPressure":
        allowed = {
            "entity_count",
            "account_count",
            "required_mutations",
            "distractor_policies",
            "negative_constraints",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(
                f"unknown dependency world pressure fields: {sorted(unknown)}"
            )
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _ticket_id(index: int) -> str:
    return f"TKT-{index:04d}"


def _account_id(index: int) -> str:
    return f"ACC-{index:04d}"


def _matching_signal(
    rng: random.Random,
    severity_threshold: int,
    age_threshold: int,
) -> tuple[int, int]:
    if rng.choice([True, False]):
        return (
            rng.randint(severity_threshold, 5),
            rng.randint(1, max(1, age_threshold - 1)),
        )
    return (
        rng.randint(1, max(1, severity_threshold - 1)),
        rng.randint(age_threshold, age_threshold + 72),
    )


def _below_signal(
    rng: random.Random,
    severity_threshold: int,
    age_threshold: int,
) -> tuple[int, int]:
    return (
        rng.randint(1, max(1, severity_threshold - 1)),
        rng.randint(1, max(1, age_threshold - 1)),
    )


def _ticket_row(
    *,
    index: int,
    account_id: str,
    product: str,
    severity: int,
    age_hours: int,
    status: str,
) -> tuple[Any, ...]:
    return (
        _ticket_id(index),
        account_id,
        product,
        severity,
        age_hours,
        status,
        "normal",
        "queue",
        "",
        f"Generated dependency support case {index}",
    )


def _write_policy(
    path: Path,
    *,
    eligible_plans: tuple[str, ...],
    severity_threshold: int,
    age_threshold: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Current escalation policy\n\n"
        f"Eligible support plans: {', '.join(eligible_plans)}.\n\n"
        f"Severity threshold: {severity_threshold}.\n"
        f"Age threshold hours: {age_threshold}.\n\n"
        "Escalate a ticket only when all of the following are true:\n\n"
        "1. `status` is exactly `open`;\n"
        "2. `severity` meets the severity threshold OR `age_hours` meets the age threshold;\n"
        "3. the owning account's `support_plan` is one of the eligible plans above;\n"
        "4. the ticket `product` is active for the owning account's `region` in "
        "`routing/current_coverage.json`.\n\n"
        "Ticket rows intentionally do not contain account plan or region. Resolve the "
        "ticket's `account_id` with the benchmark world API before deciding.\n\n"
        "For each matching ticket apply the API escalation action, which sets exactly:\n\n"
        "- `priority = urgent`\n"
        "- `assignee = oncall`\n"
        "- `escalation_reason = policy_match`\n\n"
        "Do not change non-matching tickets, accounts, database schema, policy files, "
        "or routing files.\n",
        encoding="utf-8",
    )


def _write_distractor_policies(
    workspace: Path,
    *,
    rng: random.Random,
    count: int,
    plans: tuple[str, ...],
) -> list[str]:
    created: list[str] = []
    for index in range(count):
        path = workspace / "policies" / "archive" / f"escalation_{2023 + index}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Archived entitlement escalation policy\n\n"
            "Historical only. Do not use this file for the current workflow.\n\n"
            f"Eligible support plans: {', '.join(rng.sample(list(plans), 2))}.\n"
            f"Severity threshold: {rng.choice([2, 3])}.\n"
            f"Age threshold hours: {rng.choice([8, 12, 18])}.\n",
            encoding="utf-8",
        )
        created.append(path.relative_to(workspace).as_posix())
    return created


def _choose_inactive_product(
    rng: random.Random,
    *,
    region: str,
    products: tuple[str, ...],
    active_product_by_region: Mapping[str, str],
) -> str:
    inactive = [
        product
        for product in products
        if product != active_product_by_region[region]
    ]
    return rng.choice(inactive)


def generate_dependency_world_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: DependencyWorldPressure,
) -> dict[str, Any]:
    """Generate a support world whose decision requires a multi-source information join."""

    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / "world").mkdir(parents=True, exist_ok=True)

    rng = random.Random(_derived_seed(seed, "support-dependency-world"))
    plans = ("platinum", "gold", "standard", "basic")
    regions = ("eu", "us", "apac")
    products = ("compute", "storage", "network")
    eligible_plans = tuple(sorted(rng.sample(plans, 2)))
    ineligible_plans = tuple(plan for plan in plans if plan not in eligible_plans)
    severity_threshold = rng.choice([3, 4])
    age_threshold = rng.choice([24, 36, 48])
    active_product_by_region = {
        region: rng.choice(products)
        for region in regions
    }
    active_coverage = sorted(
        (
            {"region": region, "product": product}
            for region, product in active_product_by_region.items()
        ),
        key=lambda item: (item["region"], item["product"]),
    )

    account_rows: list[tuple[str, str, str, str]] = []
    for index in range(1, pressure.account_count + 1):
        if index <= 2:
            plan = rng.choice(eligible_plans)
        elif index <= 4:
            plan = rng.choice(ineligible_plans)
        else:
            plan = rng.choice(plans)
        region = rng.choice(regions)
        account_rows.append(
            (
                _account_id(index),
                plan,
                region,
                f"Generated account {index}",
            )
        )
    account_map = {
        account_id: {
            "id": account_id,
            "support_plan": plan,
            "region": region,
            "name": name,
        }
        for account_id, plan, region, name in account_rows
    }
    eligible_accounts = [
        account
        for account in account_map.values()
        if account["support_plan"] in eligible_plans
    ]
    ineligible_accounts = [
        account
        for account in account_map.values()
        if account["support_plan"] not in eligible_plans
    ]
    if not eligible_accounts or not ineligible_accounts:
        raise RuntimeError("generated account pools are incomplete")

    ticket_rows: list[tuple[Any, ...]] = []
    target_ids: list[str] = []
    index = 1

    for _ in range(pressure.required_mutations):
        account = rng.choice(eligible_accounts)
        severity, age_hours = _matching_signal(
            rng,
            severity_threshold,
            age_threshold,
        )
        ticket_rows.append(
            _ticket_row(
                index=index,
                account_id=str(account["id"]),
                product=active_product_by_region[str(account["region"])],
                severity=severity,
                age_hours=age_hours,
                status="open",
            )
        )
        target_ids.append(_ticket_id(index))
        index += 1

    for near_index in range(pressure.negative_constraints):
        kind = near_index % 4
        if kind == 0:
            account = rng.choice(eligible_accounts)
            product = active_product_by_region[str(account["region"])]
            severity, age_hours = _matching_signal(
                rng,
                severity_threshold,
                age_threshold,
            )
            status = rng.choice(["closed", "resolved"])
        elif kind == 1:
            account = rng.choice(eligible_accounts)
            product = active_product_by_region[str(account["region"])]
            severity, age_hours = _below_signal(
                rng,
                severity_threshold,
                age_threshold,
            )
            status = "open"
        elif kind == 2:
            account = rng.choice(ineligible_accounts)
            product = active_product_by_region[str(account["region"])]
            severity, age_hours = _matching_signal(
                rng,
                severity_threshold,
                age_threshold,
            )
            status = "open"
        else:
            account = rng.choice(eligible_accounts)
            product = _choose_inactive_product(
                rng,
                region=str(account["region"]),
                products=products,
                active_product_by_region=active_product_by_region,
            )
            severity, age_hours = _matching_signal(
                rng,
                severity_threshold,
                age_threshold,
            )
            status = "open"
        ticket_rows.append(
            _ticket_row(
                index=index,
                account_id=str(account["id"]),
                product=product,
                severity=severity,
                age_hours=age_hours,
                status=status,
            )
        )
        index += 1

    while len(ticket_rows) < pressure.entity_count:
        kind = rng.randrange(4)
        if kind == 0:
            account = rng.choice(eligible_accounts)
            product = active_product_by_region[str(account["region"])]
            severity, age_hours = _matching_signal(
                rng,
                severity_threshold,
                age_threshold,
            )
            status = "closed"
        elif kind == 1:
            account = rng.choice(eligible_accounts)
            product = active_product_by_region[str(account["region"])]
            severity, age_hours = _below_signal(
                rng,
                severity_threshold,
                age_threshold,
            )
            status = "open"
        elif kind == 2:
            account = rng.choice(ineligible_accounts)
            product = active_product_by_region[str(account["region"])]
            severity, age_hours = _matching_signal(
                rng,
                severity_threshold,
                age_threshold,
            )
            status = "open"
        else:
            account = rng.choice(eligible_accounts)
            product = _choose_inactive_product(
                rng,
                region=str(account["region"]),
                products=products,
                active_product_by_region=active_product_by_region,
            )
            severity, age_hours = _matching_signal(
                rng,
                severity_threshold,
                age_threshold,
            )
            status = "open"
        ticket_rows.append(
            _ticket_row(
                index=index,
                account_id=str(account["id"]),
                product=product,
                severity=severity,
                age_hours=age_hours,
                status=status,
            )
        )
        index += 1

    rng.shuffle(ticket_rows)
    database = workspace / "world" / "support.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE accounts (
                id TEXT PRIMARY KEY,
                support_plan TEXT NOT NULL,
                region TEXT NOT NULL,
                name TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE tickets (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                product TEXT NOT NULL,
                severity INTEGER NOT NULL,
                age_hours INTEGER NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                assignee TEXT NOT NULL,
                escalation_reason TEXT NOT NULL,
                subject TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO accounts (id, support_plan, region, name) VALUES (?, ?, ?, ?)",
            account_rows,
        )
        connection.executemany(
            """
            INSERT INTO tickets (
                id, account_id, product, severity, age_hours, status,
                priority, assignee, escalation_reason, subject
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ticket_rows,
        )
        connection.commit()
        connection.row_factory = sqlite3.Row
        baseline_accounts = [
            _row_dict(row)
            for row in connection.execute("SELECT * FROM accounts ORDER BY id")
        ]
        baseline_rows = [
            _row_dict(row)
            for row in connection.execute("SELECT * FROM tickets ORDER BY id")
        ]
        schema_sql = {
            table: str(
                connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()[0]
            )
            for table in ("accounts", "tickets")
        }

    policy = workspace / "policies" / "current_escalation.md"
    _write_policy(
        policy,
        eligible_plans=eligible_plans,
        severity_threshold=severity_threshold,
        age_threshold=age_threshold,
    )
    distractors = _write_distractor_policies(
        workspace,
        rng=rng,
        count=pressure.distractor_policies,
        plans=plans,
    )
    coverage = workspace / "routing" / "current_coverage.json"
    coverage.parent.mkdir(parents=True, exist_ok=True)
    coverage.write_text(
        json.dumps(
            {
                "schema": "aios-bench/support-coverage/v1",
                "active": active_coverage,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    readme = workspace / "README.md"
    readme.write_text(
        "# Support entitlement workflow\n\n"
        "The operational state is benchmark-owned while the task runs and is exposed "
        "through `tools/world_api.py`.\n"
        "Use `policies/current_escalation.md` for the current decision rule and "
        "`routing/current_coverage.json` for current product coverage.\n"
        "Ticket records contain an `account_id`; account plan and region are available "
        "only through the world API account lookup.\n"
        "Files under `policies/archive/` are historical distractors.\n"
        "No single source contains the full decision. Join ticket state, account lookup, "
        "current policy, and current coverage before applying any action.\n",
        encoding="utf-8",
    )

    protected = [
        "README.md",
        "policies/current_escalation.md",
        "routing/current_coverage.json",
        *distractors,
    ]
    expected_mutations = {
        ticket_id: {
            "priority": "urgent",
            "assignee": "oncall",
            "escalation_reason": "policy_match",
        }
        for ticket_id in sorted(target_ids)
    }
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "dependency_world",
        "scenario": "support_entitlement_escalation",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "database_path": "world/support.db",
        "tables": ["accounts", "tickets"],
        "schema_sql": schema_sql,
        "baseline_accounts": baseline_accounts,
        "baseline_rows": baseline_rows,
        "target_ids": sorted(target_ids),
        "expected_mutations": expected_mutations,
        "protected_sha256": {
            relative: _sha256(workspace / relative)
            for relative in sorted(protected)
        },
        "decision_reference": {
            "eligible_plans": list(eligible_plans),
            "severity_threshold": severity_threshold,
            "age_threshold": age_threshold,
            "active_coverage": active_coverage,
        },
    }
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def check_dependency_world_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> tuple[bool, str]:
    """Verify the exact joined-world outcome and preservation constraints."""

    try:
        if oracle.get("family") != "dependency_world":
            return False, "dependency world oracle family mismatch"
        if oracle.get("scenario") != "support_entitlement_escalation":
            return False, "unknown dependency world scenario"

        protected = oracle.get("protected_sha256")
        if not isinstance(protected, Mapping):
            return False, "missing protected source digests"
        for relative, expected_digest in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or _sha256(path) != str(expected_digest):
                return False, f"protected source modified: {relative}"

        database = workspace / str(oracle.get("database_path", ""))
        if not database.is_file():
            return False, "dependency world database missing"

        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            expected_tables = list(oracle.get("tables") or [])
            if tables != expected_tables:
                return False, f"unexpected database tables: {tables}"
            schema_value = oracle.get("schema_sql")
            if not isinstance(schema_value, Mapping):
                return False, "missing dependency world schema oracle"
            for table in expected_tables:
                schema_row = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if schema_row is None or str(schema_row[0]) != str(schema_value.get(table, "")):
                    return False, f"database schema modified: {table}"
            current_accounts = {
                str(row["id"]): _row_dict(row)
                for row in connection.execute("SELECT * FROM accounts ORDER BY id")
            }
            current_tickets = {
                str(row["id"]): _row_dict(row)
                for row in connection.execute("SELECT * FROM tickets ORDER BY id")
            }

        baseline_accounts_value = oracle.get("baseline_accounts")
        baseline_rows_value = oracle.get("baseline_rows")
        expected_mutations = oracle.get("expected_mutations")
        if (
            not isinstance(baseline_accounts_value, list)
            or not isinstance(baseline_rows_value, list)
            or not isinstance(expected_mutations, Mapping)
        ):
            return False, "invalid dependency world oracle"
        baseline_accounts = {
            str(row["id"]): dict(row)
            for row in baseline_accounts_value
            if isinstance(row, Mapping) and "id" in row
        }
        baseline_tickets = {
            str(row["id"]): dict(row)
            for row in baseline_rows_value
            if isinstance(row, Mapping) and "id" in row
        }
        if current_accounts != baseline_accounts:
            return False, "account state modified"
        if set(current_tickets) != set(baseline_tickets):
            return False, "ticket row set changed"

        mutable_fields = {"priority", "assignee", "escalation_reason"}
        for ticket_id, baseline in baseline_tickets.items():
            current = current_tickets[ticket_id]
            mutation = expected_mutations.get(ticket_id)
            if mutation is None:
                if current != baseline:
                    return False, f"non-target ticket modified: {ticket_id}"
                continue
            if not isinstance(mutation, Mapping):
                return False, f"invalid expected mutation for {ticket_id}"
            for field, baseline_value in baseline.items():
                if field not in mutable_fields and current.get(field) != baseline_value:
                    return False, f"immutable ticket field modified: {ticket_id}.{field}"
            for field in mutable_fields:
                if current.get(field) != mutation.get(field):
                    return False, f"target ticket not correctly escalated: {ticket_id}.{field}"

        report = workspace / "reports" / "escalation_summary.md"
        if not report.is_file():
            return False, "escalation audit report missing"
        reported_ids = set(
            re.findall(
                r"\bTKT-\d{4}\b",
                report.read_text(encoding="utf-8", errors="replace"),
            )
        )
        expected_ids = {str(value) for value in oracle.get("target_ids") or []}
        if reported_ids != expected_ids:
            missing = sorted(expected_ids - reported_ids)
            extra = sorted(reported_ids - expected_ids)
            return (
                False,
                f"audit report ticket set mismatch: missing={missing}, extra={extra}",
            )

        return (
            True,
            "support dependency world final state and information-chain constraints verified",
        )
    except (OSError, sqlite3.Error, TypeError, ValueError, KeyError) as exc:
        return False, (
            "dependency world parametric oracle error: "
            f"{type(exc).__name__}: {exc}"
        )
