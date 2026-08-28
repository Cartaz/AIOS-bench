from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from dataclasses import asdict, dataclass
from decimal import InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from ..reference_checks_core import eval_path, run


@dataclass(frozen=True)
class ExpensePressure:
    """Pressure coordinates for the first Frontier v4 parametric family.

    Coordinates are descriptive workload variables, not an assumed monotonic
    difficulty scale.
    """

    rows: int = 48
    malformed_rows: int = 2
    distractor_files: int = 3
    months: int = 6

    def __post_init__(self) -> None:
        if not 8 <= self.rows <= 1000:
            raise ValueError("rows must be between 8 and 1000")
        if not 1 <= self.malformed_rows <= min(32, self.rows // 3):
            raise ValueError("malformed_rows must be between 1 and min(32, rows//3)")
        if not 0 <= self.distractor_files <= 32:
            raise ValueError("distractor_files must be between 0 and 32")
        if not 2 <= self.months <= 12:
            raise ValueError("months must be between 2 and 12")
        if self.rows - self.malformed_rows < self.months:
            raise ValueError("rows must leave at least one valid transaction per month")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExpensePressure":
        allowed = {"rows", "malformed_rows", "distractor_files", "months"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown expense pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _money(cents: int) -> str:
    return f"{cents / 100:.2f}"


def _make_rows(seed: int, *, rows: int, malformed_rows: int, months: int) -> tuple[list[list[str]], dict[str, str]]:
    rng = random.Random(seed)
    merchants = [
        "Northwind Office", "Metro Transit", "Harbor Hotel", "Pine Labs",
        "Atlas Telecom", "Cedar Market", "Delta Hosting", "Juniper Travel",
    ]
    categories = ["office", "travel", "hosting", "meals", "transport", "telecom"]
    valid_rows = rows - malformed_rows
    totals: dict[str, int] = {f"2026-{month:02d}": 0 for month in range(1, months + 1)}
    generated: list[list[str]] = []

    # Guarantee every month is represented, then fill remaining rows randomly.
    month_plan = list(range(1, months + 1))
    month_plan.extend(rng.randint(1, months) for _ in range(valid_rows - months))
    rng.shuffle(month_plan)
    for index, month in enumerate(month_plan, 1):
        day = rng.randint(1, 28)
        cents = rng.randint(125, 48_000)
        month_key = f"2026-{month:02d}"
        totals[month_key] += cents
        generated.append([
            f"2026-{month:02d}-{day:02d}",
            rng.choice(merchants),
            rng.choice(categories),
            _money(cents),
        ])

    for malformed_index in range(malformed_rows):
        month = rng.randint(1, months)
        day = rng.randint(1, 28)
        generated.append([
            f"2026-{month:02d}-{day:02d}",
            f"Malformed Merchant {malformed_index + 1}",
            rng.choice(categories),
            rng.choice(["not-a-number", "", "12.3.4", "N/A"]),
        ])
    rng.shuffle(generated)
    return generated, {month: _money(cents) for month, cents in sorted(totals.items())}


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["date", "merchant", "category", "amount"])
        writer.writerows(rows)


def _write_distractors(workspace: Path, *, seed: int, count: int, months: int) -> list[str]:
    rng = random.Random(seed)
    created: list[str] = []
    archive = workspace / "data" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        path = archive / f"historical_expenses_{index + 1:02d}.csv"
        rows: list[list[str]] = []
        for _ in range(rng.randint(4, 10)):
            month = rng.randint(1, months)
            rows.append([
                f"2024-{month:02d}-{rng.randint(1, 28):02d}",
                f"Historical Vendor {rng.randint(1, 20)}",
                "archive",
                _money(rng.randint(100, 25_000)),
            ])
        _write_csv(path, rows)
        created.append(path.relative_to(workspace).as_posix())
    return created


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_expense_variant(workspace: Path, *, seed: int, pressure: ExpensePressure) -> dict[str, Any]:
    """Materialize a deterministic expense-report task variant and return its hidden oracle."""
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / "tools").mkdir(parents=True, exist_ok=True)

    primary_rows, primary_totals = _make_rows(
        _derived_seed(seed, "primary"),
        rows=pressure.rows,
        malformed_rows=pressure.malformed_rows,
        months=pressure.months,
    )
    alternate_rows_count = max(8, pressure.rows // 2)
    alternate_malformed = max(1, min(pressure.malformed_rows, alternate_rows_count // 4))
    alternate_rows, alternate_totals = _make_rows(
        _derived_seed(seed, "alternate"),
        rows=alternate_rows_count,
        malformed_rows=alternate_malformed,
        months=pressure.months,
    )

    primary = workspace / "data" / "transactions.csv"
    alternate = workspace / "data" / "transactions_alt.csv"
    _write_csv(primary, primary_rows)
    _write_csv(alternate, alternate_rows)
    distractors = _write_distractors(
        workspace,
        seed=_derived_seed(seed, "distractors"),
        count=pressure.distractor_files,
        months=pressure.months,
    )
    readme = workspace / "data" / "README.md"
    readme.write_text(
        "# Transaction inputs\n\n"
        "`transactions.csv` is the authoritative dataset for the requested report.\n"
        "`transactions_alt.csv` is the authoritative alternate validation dataset.\n"
        "Files under `archive/` are historical distractors and must not be used for current totals.\n",
        encoding="utf-8",
    )

    protected = [
        "data/transactions.csv",
        "data/transactions_alt.csv",
        "data/README.md",
        *distractors,
    ]
    source_sha256 = {relative: _sha256(workspace / relative) for relative in sorted(protected)}
    parameters = pressure.to_dict()
    oracle_core: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "expense_report",
        "seed": int(seed),
        "parameters": parameters,
        "primary": {
            "path": "data/transactions.csv",
            "malformed_rows": pressure.malformed_rows,
            "monthly_totals": primary_totals,
        },
        "alternate": {
            "path": "data/transactions_alt.csv",
            "malformed_rows": alternate_malformed,
            "monthly_totals": alternate_totals,
        },
        "protected_sha256": source_sha256,
    }
    oracle_core["variant_digest"] = _canonical_digest(oracle_core)
    return oracle_core


def _report_has_expected(text: str, monthly_totals: Mapping[str, str], malformed_rows: int) -> bool:
    for month, total in monthly_totals.items():
        if month not in text or total not in text:
            return False
    malformed_pattern = re.compile(
        rf"(?:skipped|malformed|invalid).{{0,50}}\b{int(malformed_rows)}\b",
        re.IGNORECASE | re.DOTALL,
    )
    return malformed_pattern.search(text) is not None


def check_expense_variant(workspace: Path, oracle: Mapping[str, Any]) -> tuple[bool, str]:
    """Check source integrity and transfer of the generated expense-report tool."""
    try:
        if oracle.get("family") != "expense_report":
            return False, "expense oracle family mismatch"
        protected = oracle.get("protected_sha256")
        if not isinstance(protected, Mapping):
            return False, "missing protected source digests"
        for relative, expected_digest in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or _sha256(path) != str(expected_digest):
                return False, f"protected source modified: {relative}"

        tool = workspace / "tools" / "expense_report.py"
        report = workspace / "reports" / "monthly_expense_report.md"
        if not tool.is_file() or not report.is_file():
            return False, "required expense artifacts missing"

        primary = oracle.get("primary") or {}
        alternate = oracle.get("alternate") or {}
        generated_primary = eval_path(workspace, "v4_expense_primary.md")
        generated_alternate = eval_path(workspace, "v4_expense_alternate.md")
        first = run(
            workspace,
            ["python", "tools/expense_report.py", "--input", str(primary["path"]), "--output", str(generated_primary)],
        )
        second = run(
            workspace,
            ["python", "tools/expense_report.py", "--input", str(alternate["path"]), "--output", str(generated_alternate)],
        )
        if first.returncode or second.returncode:
            return False, "expense tool failed on generated primary or alternate dataset"

        primary_text = generated_primary.read_text(encoding="utf-8", errors="replace")
        alternate_text = generated_alternate.read_text(encoding="utf-8", errors="replace")
        saved_text = report.read_text(encoding="utf-8", errors="replace")
        if not _report_has_expected(
            primary_text,
            primary.get("monthly_totals") or {},
            int(primary.get("malformed_rows", -1)),
        ):
            return False, "tool output is incorrect on generated primary dataset"
        if not _report_has_expected(
            alternate_text,
            alternate.get("monthly_totals") or {},
            int(alternate.get("malformed_rows", -1)),
        ):
            return False, "tool does not transfer to generated alternate dataset"
        if not _report_has_expected(
            saved_text,
            primary.get("monthly_totals") or {},
            int(primary.get("malformed_rows", -1)),
        ):
            return False, "saved monthly report does not match generated primary dataset"

        source = tool.read_text(encoding="utf-8", errors="replace")
        totals = {
            str(value)
            for section in (primary, alternate)
            for value in (section.get("monthly_totals") or {}).values()
        }
        suspicious = sorted(total for total in totals if total and total in source)
        if suspicious:
            return False, "expense tool contains generated fixture totals"
        return True, "generated expense variant verified on primary and alternate datasets"
    except (KeyError, TypeError, ValueError, OSError, InvalidOperation) as exc:
        return False, f"expense parametric oracle error: {type(exc).__name__}: {exc}"
