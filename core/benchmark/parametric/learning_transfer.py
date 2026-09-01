from __future__ import annotations

import csv
import hashlib
import json
import random
from copy import deepcopy
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any, Mapping, Sequence

from .grading import VariantGrade


SKILL_SCHEMA = "aios-bench/learned-reporting-skill/v1"
STATUSES = ("posted", "cleared", "approved")
GROUP_FIELDS = ("department", "region", "category")
DIRECTION_POLICIES = ("signed", "absolute", "credits_only")
THRESHOLDS = (0, 250, 500, 1000)
BASE_COLUMNS = {
    "status": "status",
    "amount": "amount_cents",
    "direction": "direction",
    "verified": "verified",
}
TRANSFER_ALIASES = {
    "status": "workflow_state",
    "group": "segment_key",
    "amount": "value_cents",
    "direction": "flow_kind",
    "verified": "is_verified",
}
PHASES = {"acquire", "transfer", "repair"}


@dataclass(frozen=True)
class LearningTransferPressure:
    """Workload coordinates for learned-procedure acquisition and reuse."""

    demo_count: int = 3
    rows_per_demo: int = 54
    evaluation_rows: int = 60
    group_count: int = 6
    distractor_columns: int = 4
    schema_shift_fields: int = 4

    def __post_init__(self) -> None:
        if not 2 <= self.demo_count <= 6:
            raise ValueError("demo_count must be between 2 and 6")
        if not 48 <= self.rows_per_demo <= 120:
            raise ValueError("rows_per_demo must be between 48 and 120")
        if not 24 <= self.evaluation_rows <= 200:
            raise ValueError("evaluation_rows must be between 24 and 200")
        if not 3 <= self.group_count <= 12:
            raise ValueError("group_count must be between 3 and 12")
        if not 0 <= self.distractor_columns <= 12:
            raise ValueError("distractor_columns must be between 0 and 12")
        if not 2 <= self.schema_shift_fields <= 5:
            raise ValueError("schema_shift_fields must be between 2 and 5")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LearningTransferPressure":
        allowed = {
            "demo_count",
            "rows_per_demo",
            "evaluation_rows",
            "group_count",
            "distractor_columns",
            "schema_shift_fields",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown learning-transfer pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_skill(seed: int) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "learning-transfer-skill"))
    group_field = rng.choice(GROUP_FIELDS)
    return {
        "schema": SKILL_SCHEMA,
        "columns": {**BASE_COLUMNS, "group": group_field},
        "rules": {
            "required_status": rng.choice(STATUSES),
            "minimum_abs_cents": rng.choice(THRESHOLDS),
            "direction_policy": rng.choice(DIRECTION_POLICIES),
            "require_verified": bool(rng.getrandbits(1)),
        },
    }


def _candidate_skills() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for group_field, status, threshold, policy, verified in product(
        GROUP_FIELDS,
        STATUSES,
        THRESHOLDS,
        DIRECTION_POLICIES,
        (False, True),
    ):
        result.append({
            "schema": SKILL_SCHEMA,
            "columns": {**BASE_COLUMNS, "group": group_field},
            "rules": {
                "required_status": status,
                "minimum_abs_cents": threshold,
                "direction_policy": policy,
                "require_verified": verified,
            },
        })
    return result


def _valid_skill(value: Any) -> bool:
    if not isinstance(value, Mapping) or value.get("schema") != SKILL_SCHEMA:
        return False
    columns = value.get("columns")
    rules = value.get("rules")
    if not isinstance(columns, Mapping) or not isinstance(rules, Mapping):
        return False
    if set(columns) != {"status", "group", "amount", "direction", "verified"}:
        return False
    if not all(isinstance(item, str) and item for item in columns.values()):
        return False
    if set(rules) != {
        "required_status",
        "minimum_abs_cents",
        "direction_policy",
        "require_verified",
    }:
        return False
    return bool(
        rules.get("required_status") in STATUSES
        and rules.get("minimum_abs_cents") in THRESHOLDS
        and rules.get("direction_policy") in DIRECTION_POLICIES
        and isinstance(rules.get("require_verified"), bool)
    )


def _load_skill(workspace: Path) -> dict[str, Any] | None:
    path = workspace / "skills" / "reporting_workflow.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return deepcopy(value) if _valid_skill(value) else None


def _group_values(pressure: LearningTransferPressure) -> dict[str, tuple[str, ...]]:
    return {
        "department": tuple(f"dept-{index:02d}" for index in range(1, pressure.group_count + 1)),
        "region": tuple(f"region-{index:02d}" for index in range(1, pressure.group_count + 1)),
        "category": tuple(f"cat-{index:02d}" for index in range(1, pressure.group_count + 1)),
    }


def _semantic_rows(
    *,
    seed: int,
    count: int,
    pressure: LearningTransferPressure,
    label: str,
) -> list[dict[str, Any]]:
    rng = random.Random(_derived_seed(seed, label))
    groups = _group_values(pressure)
    teaching = list(product(STATUSES, (100, 300, 600, 1200), ("credit", "debit"), (False, True)))
    rng.shuffle(teaching)
    random_amounts = (50, 175, 275, 525, 875, 1300, 2400, 5200)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        if index < len(teaching):
            status, amount, direction, verified = teaching[index]
        else:
            status = rng.choice(STATUSES)
            amount = rng.choice(random_amounts)
            direction = rng.choice(("credit", "debit"))
            verified = bool(rng.getrandbits(1))
        row: dict[str, Any] = {
            "record_id": f"R{index + 1:04d}",
            "status": status,
            "department": groups["department"][index % pressure.group_count],
            "region": groups["region"][(index * 2 + 1) % pressure.group_count],
            "category": groups["category"][(index * 5 + 3) % pressure.group_count],
            "amount_cents": amount,
            "direction": direction,
            "verified": verified,
        }
        for noise in range(1, pressure.distractor_columns + 1):
            row[f"noise_{noise:02d}"] = rng.choice(
                (f"decoy-{rng.randint(1, 9)}", str(rng.randint(-30, 30)), "unused")
            )
        rows.append(row)
    return rows


def _cell_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _row_contribution(
    skill: Mapping[str, Any],
    row: Mapping[str, Any],
) -> tuple[str, int] | None:
    columns = skill["columns"]
    rules = skill["rules"]
    if str(row[columns["status"]]) != rules["required_status"]:
        return None
    if rules["require_verified"] and not _cell_bool(row[columns["verified"]]):
        return None
    amount = int(row[columns["amount"]])
    if abs(amount) < int(rules["minimum_abs_cents"]):
        return None
    direction = str(row[columns["direction"]])
    policy = str(rules["direction_policy"])
    if policy == "credits_only" and direction != "credit":
        return None
    signed = abs(amount)
    if policy == "signed" and direction == "debit":
        signed = -signed
    return str(row[columns["group"]]), signed


def _apply_skill(skill: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not _valid_skill(skill):
        raise ValueError("invalid learned reporting skill")
    totals: dict[str, list[int]] = {}
    included = 0
    grand_total = 0
    for row in rows:
        contribution = _row_contribution(skill, row)
        if contribution is None:
            continue
        group, signed = contribution
        bucket = totals.setdefault(group, [0, 0])
        bucket[0] += 1
        bucket[1] += signed
        included += 1
        grand_total += signed
    return {
        "groups": [
            {"group": group, "row_count": values[0], "total_cents": values[1]}
            for group, values in sorted(totals.items())
        ],
        "included_row_count": included,
        "grand_total_cents": grand_total,
    }


def _demonstration_result(
    skill: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    included_ids = [
        str(row["record_id"])
        for row in rows
        if _row_contribution(skill, row) is not None
    ]
    return {
        "summary": _apply_skill(skill, rows),
        "included_record_ids": included_ids,
    }


def _matching_demo_skills(
    demonstrations: Sequence[tuple[Sequence[Mapping[str, Any]], Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    return [
        candidate
        for candidate in _candidate_skills()
        if all(_demonstration_result(candidate, rows) == dict(expected) for rows, expected in demonstrations)
    ]


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(fieldnames or (rows[0].keys() if rows else ()))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _skill_schema_doc() -> str:
    return (
        "# Learned reporting skill schema\n\n"
        f"The skill is JSON with `schema` equal to `{SKILL_SCHEMA}`. `columns` maps the semantic "
        "roles `status`, `group`, `amount`, `direction`, and `verified` to concrete CSV column names. "
        "`rules` contains `required_status`, `minimum_abs_cents`, `direction_policy`, and "
        "`require_verified`.\n\n"
        f"Allowed statuses: {list(STATUSES)}. Allowed minimum thresholds: {list(THRESHOLDS)}. "
        f"Allowed direction policies: {list(DIRECTION_POLICIES)}. `require_verified` is boolean. "
        "The reusable tool groups included rows by the configured group column and reports per-group "
        "`row_count`/`total_cents`, plus `included_row_count` and `grand_total_cents`. Under `signed`, "
        "debits subtract and credits add; under `absolute`, both add; under `credits_only`, debits are "
        "excluded. Demonstration expected files additionally list `included_record_ids`; those IDs are "
        "evidence for learning the procedure, not an extra field in final reports.\n"
    )


def _tool_source() -> str:
    return f'''from __future__ import annotations
import argparse, csv, json
from pathlib import Path

SCHEMA = {SKILL_SCHEMA!r}

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def cell_bool(value):
    return str(value).strip().lower() in {{"1", "true", "yes"}}

def apply(skill, rows):
    if skill.get("schema") != SCHEMA:
        raise SystemExit("invalid skill schema")
    c, r = skill["columns"], skill["rules"]
    totals, included, grand = {{}}, 0, 0
    for row in rows:
        if row[c["status"]] != r["required_status"]:
            continue
        if r["require_verified"] and not cell_bool(row[c["verified"]]):
            continue
        amount = int(row[c["amount"]])
        if abs(amount) < int(r["minimum_abs_cents"]):
            continue
        direction = row[c["direction"]]
        policy = r["direction_policy"]
        if policy == "credits_only" and direction != "credit":
            continue
        signed = abs(amount)
        if policy == "signed" and direction == "debit":
            signed = -signed
        group = row[c["group"]]
        bucket = totals.setdefault(group, [0, 0])
        bucket[0] += 1; bucket[1] += signed
        included += 1; grand += signed
    return {{"groups": [{{"group": k, "row_count": v[0], "total_cents": v[1]}} for k, v in sorted(totals.items())], "included_row_count": included, "grand_total_cents": grand}}

def main():
    p = argparse.ArgumentParser(); p.add_argument("--skill", required=True); p.add_argument("--input", required=True); p.add_argument("--output", required=True); a = p.parse_args()
    with Path(a.input).open("r", encoding="utf-8", newline="") as h: rows = list(csv.DictReader(h))
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(apply(load(a.skill), rows), indent=2, sort_keys=True) + "\\n", encoding="utf-8")
if __name__ == "__main__": main()
'''


def _write_common(workspace: Path) -> list[str]:
    (workspace / "docs").mkdir(parents=True, exist_ok=True)
    (workspace / "tools").mkdir(parents=True, exist_ok=True)
    (workspace / "docs" / "skill_schema.md").write_text(_skill_schema_doc(), encoding="utf-8")
    (workspace / "tools" / "apply_skill.py").write_text(_tool_source(), encoding="utf-8")
    return ["docs/skill_schema.md", "tools/apply_skill.py"]


def _protected(workspace: Path, paths: Sequence[str]) -> dict[str, str]:
    return {relative: _sha256(workspace / relative) for relative in sorted(set(paths))}


def _base_header(pressure: LearningTransferPressure) -> list[str]:
    return [
        "record_id",
        "status",
        "department",
        "region",
        "category",
        "amount_cents",
        "direction",
        "verified",
        *[f"noise_{index:02d}" for index in range(1, pressure.distractor_columns + 1)],
    ]


def _transfer_mapping(
    seed: int,
    pressure: LearningTransferPressure,
    skill: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    rng = random.Random(_derived_seed(seed, "learning-transfer-columns"))
    roles = ["status", "group", "amount", "direction", "verified"]
    rng.shuffle(roles)
    selected = set(roles[: pressure.schema_shift_fields])
    expected = deepcopy(skill)
    changes: dict[str, str] = {}
    for role in roles:
        if role not in selected:
            continue
        alias = TRANSFER_ALIASES[role]
        expected["columns"][role] = alias
        changes[role] = alias
    return changes, expected


def _rows_for_columns(
    rows: Sequence[Mapping[str, Any]],
    source_skill: Mapping[str, Any],
    target_skill: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rename = {
        str(source_skill["columns"][role]): str(target_skill["columns"][role])
        for role in ("status", "group", "amount", "direction", "verified")
        if source_skill["columns"][role] != target_skill["columns"][role]
    }
    return [
        {rename.get(str(key), str(key)): value for key, value in row.items()}
        for row in rows
    ]


def _rows_for_concrete_skill(
    rows: Sequence[Mapping[str, Any]],
    skill: Mapping[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        converted = dict(row)
        for role in ("status", "amount", "direction", "verified"):
            source = BASE_COLUMNS[role]
            target = str(skill["columns"][role])
            if source != target:
                converted[target] = converted.pop(source)
        group_target = str(skill["columns"]["group"])
        if group_target not in converted:
            converted[group_target] = converted.pop("department")
        result.append(converted)
    return result


def _acquire_workspace(
    workspace: Path,
    *,
    seed: int,
    pressure: LearningTransferPressure,
) -> tuple[list[str], dict[str, Any]]:
    skill = _canonical_skill(seed)
    protected = _write_common(workspace)
    (workspace / "examples").mkdir(parents=True, exist_ok=True)
    header = _base_header(pressure)
    demonstrations: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []
    for index in range(1, pressure.demo_count + 1):
        rows = _semantic_rows(
            seed=seed,
            count=pressure.rows_per_demo,
            pressure=pressure,
            label=f"learning-demo-{index}",
        )
        expected = _demonstration_result(skill, rows)
        demonstrations.append((rows, expected))
        csv_path = f"examples/demo_{index:02d}.csv"
        result_path = f"examples/demo_{index:02d}_expected.json"
        _write_csv(workspace / csv_path, rows, header)
        _write_json(workspace / result_path, expected)
        protected.extend((csv_path, result_path))
    matches = _matching_demo_skills(demonstrations)
    if matches != [skill]:
        raise RuntimeError(
            f"learning acquisition examples are not uniquely identifiable: {len(matches)} candidates"
        )

    current_rows = _semantic_rows(
        seed=seed,
        count=pressure.evaluation_rows,
        pressure=pressure,
        label="learning-acquire-current",
    )
    _write_csv(workspace / "data" / "current.csv", current_rows, header)
    protected.append("data/current.csv")
    (workspace / "README.md").write_text(
        "# Learn the recurring reporting procedure\n\n"
        "The example CSV/result pairs were produced by one reusable reporting procedure. Read "
        "`docs/skill_schema.md`, infer the unique procedure that explains every example, and persist "
        "it at `skills/reporting_workflow.json`. Then apply that learned skill to `data/current.csv` "
        "with `python tools/apply_skill.py --skill skills/reporting_workflow.json --input "
        "data/current.csv --output reports/learning_acquisition.json`. Do not modify examples, data, "
        "documentation, or the benchmark-owned tool. The examples, rows, groups and distractor columns "
        "vary by seed and pressure coordinates.\n",
        encoding="utf-8",
    )
    protected.append("README.md")
    return protected, {
        "expected_skill": skill,
        "expected_report": _apply_skill(skill, current_rows),
        "report_path": "reports/learning_acquisition.json",
        "identifiable_candidate_count": len(matches),
    }


def _transfer_workspace(
    workspace: Path,
    *,
    seed: int,
    pressure: LearningTransferPressure,
) -> tuple[list[str], dict[str, Any]]:
    prior = _load_skill(workspace) or _canonical_skill(seed)
    changes, expected_skill = _transfer_mapping(seed, pressure, prior)
    protected = _write_common(workspace)
    base_rows = _semantic_rows(
        seed=seed,
        count=pressure.evaluation_rows,
        pressure=pressure,
        label="learning-transfer-current",
    )
    shifted_rows = _rows_for_columns(base_rows, prior, expected_skill)
    _write_csv(workspace / "data" / "transfer.csv", shifted_rows, list(shifted_rows[0]))
    _write_json(
        workspace / "schema" / "current.json",
        {
            "schema": "aios-bench/schema-transition/v1",
            "semantic_column_changes": changes,
            "unchanged_rule_semantics": True,
        },
    )
    protected.extend(("data/transfer.csv", "schema/current.json"))
    (workspace / "README.md").write_text(
        "# Transfer the learned procedure\n\n"
        "Use the durable skill persisted by the preceding learning task. The learned reporting rules "
        "are intentionally not repeated here. `schema/current.json` describes the semantic column "
        "changes in the new dataset. Adapt only the affected `columns` entries in "
        "`skills/reporting_workflow.json`; preserve every learned rule. Then apply the updated skill "
        "to `data/transfer.csv` and save the summary at `reports/learning_transfer.json`. Do not "
        "modify the schema document, data, documentation, or benchmark-owned tool.\n",
        encoding="utf-8",
    )
    protected.append("README.md")
    return protected, {
        "expected_skill": expected_skill,
        "expected_report": _apply_skill(expected_skill, shifted_rows),
        "report_path": "reports/learning_transfer.json",
        "adapted_columns": changes,
    }


def _corrupt_skill(skill: Mapping[str, Any], seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    rng = random.Random(_derived_seed(seed, "learning-repair-corruption"))
    corrupted = deepcopy(skill)
    fields = ["required_status", "minimum_abs_cents", "direction_policy", "require_verified"]
    field = rng.choice(fields)
    correct = corrupted["rules"][field]
    if field == "required_status":
        wrong = rng.choice([value for value in STATUSES if value != correct])
    elif field == "minimum_abs_cents":
        wrong = rng.choice([value for value in THRESHOLDS if value != correct])
    elif field == "direction_policy":
        wrong = rng.choice([value for value in DIRECTION_POLICIES if value != correct])
    else:
        wrong = not bool(correct)
    corrupted["rules"][field] = wrong
    return corrupted, {"field": field, "previous": wrong, "current": correct}


def _repair_workspace(
    workspace: Path,
    *,
    seed: int,
    pressure: LearningTransferPressure,
) -> tuple[list[str], dict[str, Any]]:
    prior = _load_skill(workspace)
    if prior is None:
        base = _canonical_skill(seed)
        _, prior = _transfer_mapping(seed, pressure, base)
    expected_skill = deepcopy(prior)
    corrupted, correction = _corrupt_skill(expected_skill, seed)
    _write_json(workspace / "skills" / "reporting_workflow.json", corrupted)
    protected = _write_common(workspace)

    for index in range(1, 4):
        rows = _semantic_rows(
            seed=seed,
            count=max(48, pressure.rows_per_demo),
            pressure=pressure,
            label=f"learning-repair-validation-{index}",
        )
        concrete = _rows_for_concrete_skill(rows, expected_skill)
        csv_path = f"validation/case_{index:02d}.csv"
        result_path = f"validation/case_{index:02d}_expected.json"
        _write_csv(workspace / csv_path, concrete, list(concrete[0]))
        _write_json(workspace / result_path, _demonstration_result(expected_skill, concrete))
        protected.extend((csv_path, result_path))

    current_rows = _semantic_rows(
        seed=seed,
        count=pressure.evaluation_rows,
        pressure=pressure,
        label="learning-repair-current",
    )
    concrete_current = _rows_for_concrete_skill(current_rows, expected_skill)
    _write_csv(workspace / "data" / "current.csv", concrete_current, list(concrete_current[0]))
    protected.append("data/current.csv")

    (workspace / "README.md").write_text(
        "# Repair the learned procedure\n\n"
        "Exactly one rule in the persisted `skills/reporting_workflow.json` was silently corrupted "
        "before this task. Use the three validation CSV/expected-result pairs to identify and correct "
        "the bad rule in the reusable skill itself. Demonstration result files contain `summary` and "
        "`included_record_ids`. Do not merely patch the final output. After the skill is corrected, "
        "apply it to `data/current.csv` and save `reports/learning_correction.json` with keys `summary`, "
        "`correction`, and `validation_cases_passed`; `correction` must contain `field`, `previous`, and "
        "`current`. Preserve all validation/data/documentation/tool inputs.\n",
        encoding="utf-8",
    )
    protected.append("README.md")
    return protected, {
        "expected_skill": expected_skill,
        "expected_report": {
            "summary": _apply_skill(expected_skill, concrete_current),
            "correction": correction,
            "validation_cases_passed": 3,
        },
        "report_path": "reports/learning_correction.json",
        "correction": correction,
    }


def generate_learning_transfer_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: LearningTransferPressure,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    phase = str((context or {}).get("phase", "acquire"))
    if phase not in PHASES:
        raise ValueError(f"unknown learning-transfer phase: {phase}")
    if phase == "acquire":
        protected_paths, expected = _acquire_workspace(workspace, seed=seed, pressure=pressure)
    elif phase == "transfer":
        protected_paths, expected = _transfer_workspace(workspace, seed=seed, pressure=pressure)
    else:
        protected_paths, expected = _repair_workspace(workspace, seed=seed, pressure=pressure)

    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "learning_transfer",
        "scenario": "learned_reporting_workflow",
        "phase": phase,
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "expected_skill": expected["expected_skill"],
        "expected_report": expected["expected_report"],
        "report_path": expected["report_path"],
        "protected_sha256": _protected(workspace, protected_paths),
    }
    for key in ("adapted_columns", "correction", "identifiable_candidate_count"):
        if key in expected:
            oracle[key] = expected[key]
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def _load_json_object(path: Path, label: str) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"{label} missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{label} invalid: {type(exc).__name__}"
    if not isinstance(value, dict):
        return None, f"{label} must be a JSON object"
    return value, None


def grade_learning_transfer_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> VariantGrade:
    protected = oracle.get("protected_sha256")
    if not isinstance(protected, Mapping):
        return VariantGrade.binary(False, "learning-transfer oracle missing protected hashes")
    for relative, expected in protected.items():
        path = workspace / str(relative)
        if not path.is_file():
            return VariantGrade.binary(False, f"protected source missing: {relative}")
        if _sha256(path) != str(expected):
            return VariantGrade.binary(False, f"protected source modified: {relative}")

    skill, error = _load_json_object(
        workspace / "skills" / "reporting_workflow.json",
        "learned skill",
    )
    if skill is None:
        return VariantGrade.binary(False, str(error))
    expected_skill = oracle.get("expected_skill")
    if not isinstance(expected_skill, Mapping) or skill != dict(expected_skill):
        return VariantGrade.binary(False, "learned skill does not match the canonical reusable procedure")

    report_path = oracle.get("report_path")
    if not isinstance(report_path, str) or not report_path:
        return VariantGrade.binary(False, "learning-transfer oracle missing report path")
    report, error = _load_json_object(workspace / report_path, "learning report")
    if report is None:
        return VariantGrade.binary(False, str(error))
    expected_report = oracle.get("expected_report")
    if not isinstance(expected_report, Mapping) or report != dict(expected_report):
        return VariantGrade.binary(False, "learning report does not match the canonical transferred result")

    current_path = (
        workspace / "data" / "transfer.csv"
        if oracle.get("phase") == "transfer"
        else workspace / "data" / "current.csv"
    )
    if current_path.is_file():
        recomputed = _apply_skill(skill, _read_csv(current_path))
        expected_summary = (
            expected_report.get("summary")
            if oracle.get("phase") == "repair"
            else expected_report
        )
        if recomputed != expected_summary:
            return VariantGrade.binary(False, "persisted skill cannot reproduce the required current result")

    return VariantGrade.binary(True, f"learning-transfer {oracle.get('phase')} phase verified")


__all__ = [
    "LearningTransferPressure",
    "SKILL_SCHEMA",
    "generate_learning_transfer_variant",
    "grade_learning_transfer_variant",
]
