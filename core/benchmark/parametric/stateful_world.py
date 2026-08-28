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
class StatefulWorldPressure:
    """Workload coordinates for deterministic state-changing support worlds."""

    entity_count: int = 24
    required_mutations: int = 5
    distractor_policies: int = 3
    negative_constraints: int = 4

    def __post_init__(self) -> None:
        if not 8 <= self.entity_count <= 500:
            raise ValueError("entity_count must be between 8 and 500")
        if not 1 <= self.required_mutations <= min(64, self.entity_count // 2):
            raise ValueError("required_mutations must be between 1 and min(64, entity_count//2)")
        if not 0 <= self.distractor_policies <= 16:
            raise ValueError("distractor_policies must be between 0 and 16")
        if not 1 <= self.negative_constraints <= 64:
            raise ValueError("negative_constraints must be between 1 and 64")
        if self.required_mutations + self.negative_constraints > self.entity_count - 2:
            raise ValueError(
                "entity_count must leave at least two filler entities beyond targets and negative constraints"
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "StatefulWorldPressure":
        allowed = {
            "entity_count",
            "required_mutations",
            "distractor_policies",
            "negative_constraints",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown stateful world pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _ticket_id(index: int) -> str:
    return f"TKT-{index:04d}"


def _target_row(
    rng: random.Random,
    *,
    index: int,
    eligible_tiers: tuple[str, ...],
    severity_threshold: int,
    age_threshold: int,
) -> tuple[Any, ...]:
    severity_match = rng.choice([True, False])
    severity = rng.randint(severity_threshold, 5) if severity_match else rng.randint(1, severity_threshold - 1)
    age_hours = rng.randint(1, age_threshold - 1) if severity_match else rng.randint(age_threshold, age_threshold + 72)
    return (
        _ticket_id(index),
        rng.choice(eligible_tiers),
        severity,
        age_hours,
        "open",
        "normal",
        "queue",
        "",
        f"Generated support case {index}",
    )


def _near_miss_row(
    rng: random.Random,
    *,
    index: int,
    kind: int,
    eligible_tiers: tuple[str, ...],
    excluded_tiers: tuple[str, ...],
    severity_threshold: int,
    age_threshold: int,
) -> tuple[Any, ...]:
    if kind % 3 == 0:
        tier = rng.choice(eligible_tiers)
        severity = rng.randint(severity_threshold, 5)
        age_hours = rng.randint(age_threshold, age_threshold + 72)
        status = rng.choice(["closed", "resolved"])
    elif kind % 3 == 1:
        tier = rng.choice(excluded_tiers)
        severity = rng.randint(severity_threshold, 5)
        age_hours = rng.randint(age_threshold, age_threshold + 72)
        status = "open"
    else:
        tier = rng.choice(eligible_tiers)
        severity = rng.randint(1, severity_threshold - 1)
        age_hours = rng.randint(1, age_threshold - 1)
        status = "open"
    return (
        _ticket_id(index),
        tier,
        severity,
        age_hours,
        status,
        "normal",
        "queue",
        "",
        f"Generated support case {index}",
    )


def _filler_row(
    rng: random.Random,
    *,
    index: int,
    eligible_tiers: tuple[str, ...],
    excluded_tiers: tuple[str, ...],
    severity_threshold: int,
    age_threshold: int,
) -> tuple[Any, ...]:
    if rng.random() < 0.5:
        tier = rng.choice(excluded_tiers)
        severity = rng.randint(1, 5)
        age_hours = rng.randint(1, age_threshold + 72)
        status = rng.choice(["open", "closed", "resolved"])
    else:
        tier = rng.choice(eligible_tiers)
        severity = rng.randint(1, severity_threshold - 1)
        age_hours = rng.randint(1, age_threshold - 1)
        status = rng.choice(["open", "closed", "resolved"])
    return (
        _ticket_id(index),
        tier,
        severity,
        age_hours,
        status,
        "normal",
        "queue",
        "",
        f"Generated support case {index}",
    )


def _write_policy(
    path: Path,
    *,
    eligible_tiers: tuple[str, ...],
    severity_threshold: int,
    age_threshold: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Current escalation policy\n\n"
        f"Eligible customer tiers: {', '.join(eligible_tiers)}.\n\n"
        "A ticket must be escalated only when all of the following are true:\n\n"
        "1. `status` is exactly `open`;\n"
        "2. `customer_tier` is one of the eligible tiers above;\n"
        f"3. `severity >= {severity_threshold}` OR `age_hours >= {age_threshold}`.\n\n"
        "For each matching ticket set exactly these fields:\n\n"
        "- `priority = urgent`\n"
        "- `assignee = oncall`\n"
        "- `escalation_reason = policy_match`\n\n"
        "Do not change any other field, any non-matching ticket, the database schema, or source/policy files.\n",
        encoding="utf-8",
    )


def _write_distractor_policies(
    workspace: Path,
    *,
    rng: random.Random,
    count: int,
    eligible_tiers: tuple[str, ...],
) -> list[str]:
    created: list[str] = []
    for index in range(count):
        path = workspace / "policies" / "archive" / f"escalation_{2024 + index}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Archived escalation policy\n\n"
            "This file is historical and is not authoritative for the current workflow.\n\n"
            f"Eligible customer tiers: {', '.join(reversed(eligible_tiers))}.\n"
            f"Escalate when severity >= {rng.randint(1, 2)} or age_hours >= {rng.randint(6, 18)}.\n",
            encoding="utf-8",
        )
        created.append(path.relative_to(workspace).as_posix())
    return created


def generate_stateful_world_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: StatefulWorldPressure,
) -> dict[str, Any]:
    """Materialize a deterministic stateful support world and return its hidden oracle."""
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / "world").mkdir(parents=True, exist_ok=True)

    rng = random.Random(_derived_seed(seed, "stateful-support-world"))
    all_tiers = ("enterprise", "business", "standard", "trial")
    eligible_tiers = tuple(sorted(rng.sample(all_tiers, 2)))
    excluded_tiers = tuple(tier for tier in all_tiers if tier not in eligible_tiers)
    severity_threshold = rng.choice([3, 4])
    age_threshold = rng.choice([24, 36, 48])

    rows: list[tuple[Any, ...]] = []
    target_ids: list[str] = []
    index = 1
    for _ in range(pressure.required_mutations):
        row = _target_row(
            rng,
            index=index,
            eligible_tiers=eligible_tiers,
            severity_threshold=severity_threshold,
            age_threshold=age_threshold,
        )
        rows.append(row)
        target_ids.append(str(row[0]))
        index += 1
    for near_index in range(pressure.negative_constraints):
        rows.append(
            _near_miss_row(
                rng,
                index=index,
                kind=near_index,
                eligible_tiers=eligible_tiers,
                excluded_tiers=excluded_tiers,
                severity_threshold=severity_threshold,
                age_threshold=age_threshold,
            )
        )
        index += 1
    while len(rows) < pressure.entity_count:
        rows.append(
            _filler_row(
                rng,
                index=index,
                eligible_tiers=eligible_tiers,
                excluded_tiers=excluded_tiers,
                severity_threshold=severity_threshold,
                age_threshold=age_threshold,
            )
        )
        index += 1
    rng.shuffle(rows)

    database = workspace / "world" / "support.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE tickets (
                id TEXT PRIMARY KEY,
                customer_tier TEXT NOT NULL,
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
            """
            INSERT INTO tickets (
                id, customer_tier, severity, age_hours, status,
                priority, assignee, escalation_reason, subject
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()
        connection.row_factory = sqlite3.Row
        baseline_rows = [
            _row_dict(row)
            for row in connection.execute("SELECT * FROM tickets ORDER BY id")
        ]
        schema_sql = str(
            connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='tickets'"
            ).fetchone()[0]
        )

    policy = workspace / "policies" / "current_escalation.md"
    _write_policy(
        policy,
        eligible_tiers=eligible_tiers,
        severity_threshold=severity_threshold,
        age_threshold=age_threshold,
    )
    distractors = _write_distractor_policies(
        workspace,
        rng=rng,
        count=pressure.distractor_policies,
        eligible_tiers=eligible_tiers,
    )
    readme = workspace / "README.md"
    readme.write_text(
        "# Support operations workspace\n\n"
        "The operational state is stored in `world/support.db`.\n"
        "For this workflow, the authoritative policy is `policies/current_escalation.md`.\n"
        "Files under `policies/archive/` are historical distractors.\n"
        "Use the current policy to update the operational state and create the requested audit report.\n",
        encoding="utf-8",
    )

    protected = ["README.md", "policies/current_escalation.md", *distractors]
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
        "family": "stateful_world",
        "scenario": "support_escalation",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "database_path": "world/support.db",
        "table": "tickets",
        "schema_sql": schema_sql,
        "baseline_rows": baseline_rows,
        "target_ids": sorted(target_ids),
        "expected_mutations": expected_mutations,
        "protected_sha256": {
            relative: _sha256(workspace / relative) for relative in sorted(protected)
        },
    }
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def check_stateful_world_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> tuple[bool, str]:
    """Verify exact world-state mutation, negative constraints and audit provenance."""
    try:
        if oracle.get("family") != "stateful_world":
            return False, "stateful world oracle family mismatch"
        if oracle.get("scenario") != "support_escalation":
            return False, "unknown stateful world scenario"

        protected = oracle.get("protected_sha256")
        if not isinstance(protected, Mapping):
            return False, "missing protected source digests"
        for relative, expected_digest in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or _sha256(path) != str(expected_digest):
                return False, f"protected source modified: {relative}"

        database = workspace / str(oracle.get("database_path", ""))
        if not database.is_file():
            return False, "stateful world database missing"

        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            if tables != [str(oracle.get("table", "tickets"))]:
                return False, f"unexpected database tables: {tables}"
            schema_row = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='tickets'"
            ).fetchone()
            if schema_row is None or str(schema_row[0]) != str(oracle.get("schema_sql", "")):
                return False, "database schema modified"
            current_rows = {
                str(row["id"]): _row_dict(row)
                for row in connection.execute("SELECT * FROM tickets ORDER BY id")
            }

        baseline_value = oracle.get("baseline_rows")
        expected_mutations = oracle.get("expected_mutations")
        if not isinstance(baseline_value, list) or not isinstance(expected_mutations, Mapping):
            return False, "invalid stateful world oracle"
        baseline_rows = {
            str(row["id"]): dict(row)
            for row in baseline_value
            if isinstance(row, Mapping) and "id" in row
        }
        if set(current_rows) != set(baseline_rows):
            return False, "ticket row set changed"

        mutable_fields = {"priority", "assignee", "escalation_reason"}
        for ticket_id, baseline in baseline_rows.items():
            current = current_rows[ticket_id]
            mutation = expected_mutations.get(ticket_id)
            if mutation is None:
                if current != baseline:
                    return False, f"non-target ticket modified: {ticket_id}"
                continue
            if not isinstance(mutation, Mapping):
                return False, f"invalid expected mutation for {ticket_id}"
            for field, baseline_value_for_field in baseline.items():
                if field not in mutable_fields and current.get(field) != baseline_value_for_field:
                    return False, f"immutable ticket field modified: {ticket_id}.{field}"
            for field in mutable_fields:
                if current.get(field) != mutation.get(field):
                    return False, f"target ticket not correctly escalated: {ticket_id}.{field}"

        report = workspace / "reports" / "escalation_summary.md"
        if not report.is_file():
            return False, "escalation audit report missing"
        report_text = report.read_text(encoding="utf-8", errors="replace")
        reported_ids = set(re.findall(r"\bTKT-\d{4}\b", report_text))
        expected_ids = {str(value) for value in oracle.get("target_ids") or []}
        if reported_ids != expected_ids:
            missing = sorted(expected_ids - reported_ids)
            extra = sorted(reported_ids - expected_ids)
            return False, f"audit report ticket set mismatch: missing={missing}, extra={extra}"

        return True, "stateful support world final state and negative constraints verified"
    except (OSError, sqlite3.Error, TypeError, ValueError, KeyError) as exc:
        return False, f"stateful world parametric oracle error: {type(exc).__name__}: {exc}"
