from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .grading import VariantGrade


GROUP_FIELDS = ("account", "posted_count", "net_cents")


@dataclass(frozen=True)
class CrossArtifactPressure:
    """Concrete workload coordinates for multi-deliverable reconciliation."""

    row_count: int = 72
    group_count: int = 6
    excluded_rows: int = 12
    adjustment_rows: int = 8
    distractor_files: int = 3

    def __post_init__(self) -> None:
        if not 24 <= self.row_count <= 500:
            raise ValueError("row_count must be between 24 and 500")
        if not 2 <= self.group_count <= min(24, self.row_count // 4):
            raise ValueError("group_count must be between 2 and min(24, row_count//4)")
        if not 1 <= self.excluded_rows <= self.row_count - self.group_count:
            raise ValueError("excluded_rows must leave at least one posted row per group")
        posted_rows = self.row_count - self.excluded_rows
        if not 0 <= self.adjustment_rows <= posted_rows - self.group_count:
            raise ValueError(
                "adjustment_rows must be between 0 and posted_rows-group_count"
            )
        if not 0 <= self.distractor_files <= 12:
            raise ValueError("distractor_files must be between 0 and 12")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CrossArtifactPressure":
        allowed = {
            "row_count",
            "group_count",
            "excluded_rows",
            "adjustment_rows",
            "distractor_files",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown cross-artifact pressure fields: {sorted(unknown)}")
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


def _account(index: int) -> str:
    return f"acct-{index:02d}"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("entry_id", "account", "amount_cents", "status", "kind"),
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _summary(rows: list[dict[str, Any]], accounts: list[str]) -> dict[str, Any]:
    groups = {
        account: {"account": account, "posted_count": 0, "net_cents": 0}
        for account in accounts
    }
    total_count = 0
    total_cents = 0
    for row in rows:
        if row["status"] != "posted":
            continue
        account = str(row["account"])
        amount = int(row["amount_cents"])
        groups[account]["posted_count"] += 1
        groups[account]["net_cents"] += amount
        total_count += 1
        total_cents += amount
    return {
        "source": "source/current/ledger.csv",
        "groups": [groups[account] for account in sorted(groups)],
        "posted_count": total_count,
        "grand_total_cents": total_cents,
    }


def generate_cross_artifact_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: CrossArtifactPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    rng = random.Random(_derived_seed(seed, "cross-artifact"))
    accounts = [_account(index) for index in range(1, pressure.group_count + 1)]

    rows: list[dict[str, Any]] = []
    entry = 1
    # Guarantee at least one ordinary posted row per account.
    for account in accounts:
        rows.append({
            "entry_id": f"TX-{entry:05d}",
            "account": account,
            "amount_cents": rng.randint(1500, 90000),
            "status": "posted",
            "kind": "charge",
        })
        entry += 1

    excluded_remaining = pressure.excluded_rows
    posted_remaining = pressure.row_count - len(rows) - excluded_remaining
    adjustment_remaining = pressure.adjustment_rows
    while posted_remaining > 0:
        account = rng.choice(accounts)
        is_adjustment = adjustment_remaining > 0
        amount = -rng.randint(100, 25000) if is_adjustment else rng.randint(500, 120000)
        rows.append({
            "entry_id": f"TX-{entry:05d}",
            "account": account,
            "amount_cents": amount,
            "status": "posted",
            "kind": "adjustment" if is_adjustment else "charge",
        })
        entry += 1
        posted_remaining -= 1
        if is_adjustment:
            adjustment_remaining -= 1

    statuses = ("pending", "voided")
    while excluded_remaining > 0:
        rows.append({
            "entry_id": f"TX-{entry:05d}",
            "account": rng.choice(accounts),
            "amount_cents": rng.randint(500, 120000),
            "status": rng.choice(statuses),
            "kind": "charge",
        })
        entry += 1
        excluded_remaining -= 1

    rng.shuffle(rows)
    current_path = workspace / "source" / "current" / "ledger.csv"
    _write_csv(current_path, rows)

    for index in range(1, pressure.distractor_files + 1):
        distractor = [dict(row) for row in rows]
        if distractor:
            changed = rng.choice(distractor)
            changed["amount_cents"] = int(changed["amount_cents"]) + rng.randint(111, 9999)
            if index % 2 == 0:
                changed["status"] = "posted" if changed["status"] != "posted" else "voided"
        archive = workspace / "source" / "archive" / f"ledger_revision_{index:02d}.csv"
        _write_csv(archive, distractor)

    manifest_path = workspace / "source" / "AUTHORITY.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "aios-bench/cross-artifact-authority/v1",
                "authoritative_source": "source/current/ledger.csv",
                "rule": "Only status=posted contributes to counts and net cents.",
                "group_by": "account",
                "amount_unit": "integer cents",
                "archives_authoritative": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    instructions = workspace / "README.md"
    instructions.write_text(
        "# Cross-artifact ledger reconciliation\n\n"
        "Read `source/AUTHORITY.json` and derive one canonical account summary from the authoritative "
        "ledger. Only rows with `status=posted` count; negative posted adjustments reduce net cents. "
        "Archived ledgers are distractors and must not contribute.\n\n"
        "Produce both deliverables from the same computed source of truth:\n\n"
        "1. `reports/account_summary.json` with exactly `source`, `groups`, `posted_count`, and "
        "`grand_total_cents`. Each group contains exactly `account`, `posted_count`, and `net_cents`.\n"
        "2. `reports/account_summary.md` using exactly this semantic structure:\n"
        "   - heading `# Account summary`\n"
        "   - line `source: source/current/ledger.csv`\n"
        "   - Markdown table columns `account | posted_count | net_cents`\n"
        "   - line `posted_count: N`\n"
        "   - line `grand_total_cents: N`\n\n"
        "Include every account exactly once, include no unsupported account or claim, keep integer cents "
        "exact, and make the JSON and Markdown reconcile exactly. Do not modify existing source files.\n",
        encoding="utf-8",
    )

    expected = _summary(rows, accounts)
    protected = ["README.md", "source/AUTHORITY.json"] + [
        path.relative_to(workspace).as_posix()
        for path in sorted((workspace / "source").rglob("*.csv"))
    ]
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "cross_artifact",
        "scenario": "ledger_multi_deliverable",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "expected": expected,
        "protected_sha256": {
            relative: _sha256(workspace / relative)
            for relative in sorted(set(protected))
        },
    }
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def _normalize_groups(value: object) -> tuple[dict[str, dict[str, Any]] | None, str | None]:
    if not isinstance(value, list):
        return None, "groups must be an array"
    groups: dict[str, dict[str, Any]] = {}
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != set(GROUP_FIELDS):
            return None, "each group must contain exactly account, posted_count and net_cents"
        account = raw.get("account")
        if not isinstance(account, str) or not account or account in groups:
            return None, "group accounts must be unique non-empty strings"
        count = raw.get("posted_count")
        total = raw.get("net_cents")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            return None, f"invalid posted_count for {account}"
        if isinstance(total, bool) or not isinstance(total, int):
            return None, f"invalid net_cents for {account}"
        groups[account] = {
            "account": account,
            "posted_count": count,
            "net_cents": total,
        }
    return groups, None


def _load_json_artifact(workspace: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = workspace / "reports" / "account_summary.json"
    if not path.is_file():
        return None, "machine-readable account summary missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"machine-readable account summary invalid: {type(exc).__name__}"
    if not isinstance(value, dict) or set(value) != {
        "source", "groups", "posted_count", "grand_total_cents"
    }:
        return None, "machine-readable summary schema mismatch"
    groups, error = _normalize_groups(value.get("groups"))
    if groups is None:
        return None, error
    if value.get("source") != "source/current/ledger.csv":
        return None, "machine-readable source is not authoritative"
    for field in ("posted_count", "grand_total_cents"):
        raw = value.get(field)
        if isinstance(raw, bool) or not isinstance(raw, int):
            return None, f"machine-readable {field} must be an integer"
    return {
        "source": value["source"],
        "groups": groups,
        "posted_count": value["posted_count"],
        "grand_total_cents": value["grand_total_cents"],
    }, None


_TABLE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(-?\d+)\s*\|\s*(-?\d+)\s*\|$")
_TABLE_SEPARATOR = re.compile(
    r"^\|\s*:?-{3,}:?\s*\|\s*:?-{3,}:?\s*\|\s*:?-{3,}:?\s*\|$"
)


def _load_markdown_artifact(workspace: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = workspace / "reports" / "account_summary.md"
    if not path.is_file():
        return None, "human-readable account summary missing"
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError as exc:
        return None, f"human-readable account summary unavailable: {type(exc).__name__}"
    if not lines or lines[0] != "# Account summary":
        return None, "human-readable heading mismatch"
    if "source: source/current/ledger.csv" not in lines:
        return None, "human-readable source is not authoritative"
    try:
        header_index = lines.index("| account | posted_count | net_cents |")
    except ValueError:
        return None, "human-readable table header mismatch"
    if (
        header_index + 1 >= len(lines)
        or _TABLE_SEPARATOR.fullmatch(lines[header_index + 1]) is None
    ):
        return None, "human-readable table separator mismatch"

    groups: dict[str, dict[str, Any]] = {}
    index = header_index + 2
    while index < len(lines) and lines[index].startswith("|"):
        match = _TABLE_ROW.fullmatch(lines[index])
        if match is None:
            return None, "human-readable table row malformed"
        account = match.group(1).strip()
        if account in groups:
            return None, "human-readable account rows must be unique"
        groups[account] = {
            "account": account,
            "posted_count": int(match.group(2)),
            "net_cents": int(match.group(3)),
        }
        index += 1

    tail = lines[index:]
    if len(tail) != 2:
        return None, "human-readable summary must end with exactly two total lines"
    if not tail[0].startswith("posted_count: ") or not tail[1].startswith("grand_total_cents: "):
        return None, "human-readable total labels mismatch"
    try:
        posted_count = int(tail[0].split(":", 1)[1].strip())
        grand_total = int(tail[1].split(":", 1)[1].strip())
    except ValueError:
        return None, "human-readable totals must be integers"
    return {
        "source": "source/current/ledger.csv",
        "groups": groups,
        "posted_count": posted_count,
        "grand_total_cents": grand_total,
    }, None


def _artifact_accuracy(
    artifact: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[float, int]:
    expected_groups = {
        str(row["account"]): dict(row)
        for row in expected.get("groups") or []
        if isinstance(row, Mapping) and row.get("account") is not None
    }
    actual_groups = artifact.get("groups") if isinstance(artifact.get("groups"), Mapping) else {}
    correct = 0
    total = len(expected_groups) * 3 + 3
    if artifact.get("source") == expected.get("source"):
        correct += 1
    if artifact.get("posted_count") == expected.get("posted_count"):
        correct += 1
    if artifact.get("grand_total_cents") == expected.get("grand_total_cents"):
        correct += 1
    for account, expected_row in expected_groups.items():
        actual = actual_groups.get(account)
        if not isinstance(actual, Mapping):
            continue
        for field in GROUP_FIELDS:
            if actual.get(field) == expected_row.get(field):
                correct += 1
    extras = len(set(actual_groups) - set(expected_groups))
    return (correct / total if total else 0.0), extras


def _reconciliation_rate(
    machine: Mapping[str, Any],
    human: Mapping[str, Any],
) -> float:
    machine_groups = machine.get("groups") if isinstance(machine.get("groups"), Mapping) else {}
    human_groups = human.get("groups") if isinstance(human.get("groups"), Mapping) else {}
    accounts = set(machine_groups) | set(human_groups)
    matched = 0
    total = len(accounts) * 2 + 3
    if machine.get("source") == human.get("source"):
        matched += 1
    if machine.get("posted_count") == human.get("posted_count"):
        matched += 1
    if machine.get("grand_total_cents") == human.get("grand_total_cents"):
        matched += 1
    for account in accounts:
        left = machine_groups.get(account)
        right = human_groups.get(account)
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            continue
        if left.get("posted_count") == right.get("posted_count"):
            matched += 1
        if left.get("net_cents") == right.get("net_cents"):
            matched += 1
    return matched / total if total else 0.0


def grade_cross_artifact_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> VariantGrade:
    protected = oracle.get("protected_sha256")
    if not isinstance(protected, Mapping):
        return VariantGrade.binary(False, "cross-artifact protected-source oracle missing")
    for relative, expected_digest in protected.items():
        path = workspace / str(relative)
        if not path.is_file() or _sha256(path) != str(expected_digest):
            return VariantGrade.binary(False, f"protected source modified: {relative}")

    expected = oracle.get("expected")
    if not isinstance(expected, Mapping):
        return VariantGrade.binary(False, "cross-artifact expected summary oracle missing")
    machine, machine_error = _load_json_artifact(workspace)
    human, human_error = _load_markdown_artifact(workspace)
    if machine is None or human is None:
        detail = machine_error or human_error or "cross-artifact deliverable unavailable"
        return VariantGrade(
            passed=False,
            detail=detail,
            score=0.0,
            metrics={
                "strict_complete_pass": False,
                "machine_accuracy": 0.0 if machine is None else _artifact_accuracy(machine, expected)[0],
                "human_accuracy": 0.0 if human is None else _artifact_accuracy(human, expected)[0],
                "reconciliation_rate": 0.0,
                "machine_extra_groups": 0,
                "human_extra_groups": 0,
            },
        )

    machine_accuracy, machine_extras = _artifact_accuracy(machine, expected)
    human_accuracy, human_extras = _artifact_accuracy(human, expected)
    reconciliation = _reconciliation_rate(machine, human)
    expected_accounts = {
        str(row["account"])
        for row in expected.get("groups") or []
        if isinstance(row, Mapping) and row.get("account") is not None
    }
    machine_accounts = set(machine["groups"])
    human_accounts = set(human["groups"])
    strict = (
        machine_accuracy == 1.0
        and human_accuracy == 1.0
        and reconciliation == 1.0
        and machine_accounts == expected_accounts
        and human_accounts == expected_accounts
        and machine_extras == 0
        and human_extras == 0
    )
    score = (machine_accuracy + human_accuracy + reconciliation) / 3.0
    mismatch = reconciliation < 1.0
    metrics = {
        "strict_complete_pass": strict,
        "machine_accuracy": machine_accuracy,
        "human_accuracy": human_accuracy,
        "reconciliation_rate": reconciliation,
        "machine_extra_groups": machine_extras,
        "human_extra_groups": human_extras,
        "expected_groups": len(expected_accounts),
        "machine_groups": len(machine_accounts),
        "human_groups": len(human_accounts),
    }
    if strict:
        return VariantGrade(True, "both artifacts are correct and reconcile exactly", 1.0, metrics)
    if mismatch:
        return VariantGrade(
            False,
            "machine-readable and human-readable deliverables disagree",
            score,
            metrics,
            failure_kind="CROSS_ARTIFACT_MISMATCH",
        )
    return VariantGrade(
        False,
        "deliverables reconcile with each other but do not match the authoritative transformation",
        score,
        metrics,
    )


__all__ = [
    "CrossArtifactPressure",
    "generate_cross_artifact_variant",
    "grade_cross_artifact_variant",
]
