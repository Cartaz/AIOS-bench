from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from aios_bench.evaluators import evaluate_artifacts
from aios_bench.parametric import ExpensePressure, materialize_variant
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "tasks"


GENERIC_TOOL = '''\
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

totals = defaultdict(lambda: Decimal("0"))
malformed = 0
with Path(args.input).open(newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        try:
            amount = Decimal(row["amount"])
        except (InvalidOperation, KeyError, TypeError):
            malformed += 1
            continue
        totals[row["date"][:7]] += amount

lines = ["# Monthly expense report", ""]
for month in sorted(totals):
    lines.append(f"{month}: {totals[month]:.2f}")
lines.extend(["", f"malformed skipped: {malformed}"])
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text("\\n".join(lines) + "\\n", encoding="utf-8")
'''


def _task():
    return load_tasks(TASK_ROOT, "frontier_v4")[0]


def _write_oracle(run_dir: Path, task_id: str, oracle: dict) -> None:
    directory = run_dir / "oracles"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{task_id}.json").write_text(
        json.dumps(oracle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _install_generic_solution(workspace: Path) -> None:
    tool = workspace / "tools" / "expense_report.py"
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_text(GENERIC_TOOL, encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(tool),
            "--input",
            str(workspace / "data" / "transactions.csv"),
            "--output",
            str(workspace / "reports" / "monthly_expense_report.md"),
        ],
        cwd=workspace,
        check=True,
    )


def test_expense_variant_is_deterministic_for_same_seed(tmp_path: Path) -> None:
    pressure = ExpensePressure(rows=64, malformed_rows=3, distractor_files=4, months=8)
    a = tmp_path / "a"
    b = tmp_path / "b"
    oracle_a = materialize_variant("expense_report", a, seed=12345, parameters=pressure.to_dict())
    oracle_b = materialize_variant("expense_report", b, seed=12345, parameters=pressure.to_dict())

    assert oracle_a["variant_digest"] == oracle_b["variant_digest"]
    assert oracle_a["protected_sha256"] == oracle_b["protected_sha256"]
    for relative in oracle_a["protected_sha256"]:
        assert (a / relative).read_bytes() == (b / relative).read_bytes()


def test_expense_variant_changes_with_seed_or_pressure(tmp_path: Path) -> None:
    baseline = materialize_variant("expense_report", tmp_path / "a", seed=7)
    other_seed = materialize_variant("expense_report", tmp_path / "b", seed=8)
    other_pressure = materialize_variant(
        "expense_report",
        tmp_path / "c",
        seed=7,
        parameters={"rows": 72, "malformed_rows": 2, "distractor_files": 3, "months": 6},
    )

    assert baseline["variant_digest"] != other_seed["variant_digest"]
    assert baseline["variant_digest"] != other_pressure["variant_digest"]


def test_generated_workspace_contains_no_hidden_oracle(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("expense_report", workspace, seed=99)

    assert oracle["monthly_totals"] if "monthly_totals" in oracle else oracle["primary"]["monthly_totals"]
    assert not (workspace / "oracle.json").exists()
    assert not (workspace / "oracles").exists()
    assert all("variant_digest" not in path.read_text(encoding="utf-8", errors="ignore")
               for path in workspace.rglob("*") if path.is_file())


def test_parametric_reference_fails_untouched_and_accepts_generic_solution(tmp_path: Path) -> None:
    task = _task()
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant(
        "expense_report",
        workspace,
        seed=4242,
        parameters={"rows": 50, "malformed_rows": 3, "distractor_files": 2, "months": 5},
    )
    _write_oracle(run_dir, task.id, oracle)

    untouched = evaluate_artifacts(
        workspace,
        list(task.acceptance),
        run_dir=run_dir,
        fixture_root=ROOT / "benchmarks" / "fixtures" / "workspace",
    )
    assert untouched["passed"] is False

    _install_generic_solution(workspace)
    solved = evaluate_artifacts(
        workspace,
        list(task.acceptance),
        run_dir=run_dir,
        fixture_root=ROOT / "benchmarks" / "fixtures" / "workspace",
    )
    assert solved["passed"] is True
    assert solved["acceptance_score"] == 1.0


def test_parametric_reference_rejects_source_mutation(tmp_path: Path) -> None:
    task = _task()
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    oracle = materialize_variant("expense_report", workspace, seed=31337)
    _write_oracle(run_dir, task.id, oracle)
    _install_generic_solution(workspace)

    source = workspace / "data" / "README.md"
    source.write_text(source.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    result = evaluate_artifacts(
        workspace,
        list(task.acceptance),
        run_dir=run_dir,
        fixture_root=ROOT / "benchmarks" / "fixtures" / "workspace",
    )

    assert result["passed"] is False
    reference = next(item for item in result["results"] if item["check"]["type"] == "parametric_reference")
    assert "protected source modified" in reference["detail"]
