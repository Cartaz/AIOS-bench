from __future__ import annotations

import re
from pathlib import Path

from .fixtures import LONG_HORIZON_MIN_BYTES
from .reference_checks_core import CheckResult, eval_path, load, ok, read, run, same


def check(task_id: str, workspace: Path, fixture_root: Path) -> CheckResult:
    if task_id == "long_horizon_001":
        changelog = read(workspace, "reports/long_horizon_changelog.md")
        corpus = workspace / "research" / "long_horizon_corpus"
        corpus_bytes = (
            sum(path.stat().st_size for path in corpus.rglob("*") if path.is_file())
            if corpus.is_dir()
            else 0
        )
        validator_state = workspace / ".state/validator_runs.json"
        state = load(workspace, ".state/validator_runs.json") if validator_state.is_file() else {}
        history = state.get("history", []) if isinstance(state, dict) else []
        recovered = (
            any(
                item.get("status") == "failed"
                and item.get("error") == "validator state corruption"
                for item in history
                if isinstance(item, dict)
            )
            and int(state.get("runs", 0)) >= 4
        )
        good = (
            corpus_bytes >= LONG_HORIZON_MIN_BYTES
            and same(workspace, "tools/validator.py", fixture_root)
            and recovered
            and "validator state corruption" in changelog.lower()
            and bool(re.search(r"recovery\s*:\s*\S+", changelog, re.I))
            and all(
                (workspace / f".state/checkpoint_{number}.json").is_file()
                for number in (1, 3, 5)
            )
            and all(token in changelog for token in ("LH-047", "240 ms", "Priya N."))
        )
        return ok(
            good,
            f"large corpus ({corpus_bytes} bytes), grounded release gate, recovery and checkpoints verified",
        )

    if task_id == "long_horizon_002":
        required = [
            "tools/step1_summary.py",
            "tools/step2_chart.py",
            "tools/step3_report.py",
        ]
        if not all((workspace / path).is_file() for path in required):
            return ok(False, "pipeline stage missing")
        summary = eval_path(workspace, "lh2.json")
        chart = eval_path(workspace, "lh2.svg")
        report = eval_path(workspace, "lh2.md")
        failure = eval_path(workspace, "fail.svg")
        step1 = run(
            workspace,
            [
                "python",
                "tools/step1_summary.py",
                "--input",
                "data/expenses.csv",
                "--output",
                str(summary),
            ],
        )
        step2 = run(
            workspace,
            ["python", "tools/step2_chart.py", "--input", str(summary), "--output", str(chart)],
        )
        step3 = run(
            workspace,
            [
                "python",
                "tools/step3_report.py",
                "--summary",
                str(summary),
                "--chart",
                str(chart),
                "--output",
                str(report),
            ],
        )
        summary.unlink(missing_ok=True)
        missing_upstream = run(
            workspace,
            [
                "python",
                "tools/step2_chart.py",
                "--input",
                str(summary),
                "--output",
                str(failure),
            ],
        )
        return ok(
            step1.returncode == step2.returncode == step3.returncode == 0
            and missing_upstream.returncode != 0,
            "pipeline dependency chain verified",
        )

    if task_id == "long_horizon_003":
        matrix = load(workspace, "reports/audit_matrix.json")
        if not isinstance(matrix, list) or len(matrix) != 5:
            return ok(False, "expected five requirement rows")
        requirements = read(workspace, "notes/requirements.md")
        seen: set[str] = set()
        for entry in matrix:
            if not isinstance(entry, dict):
                return ok(False, "invalid requirement row")
            requirement_id = entry.get("requirement_id")
            quote = entry.get("evidence_quote", "")
            if requirement_id not in {f"R{index}" for index in range(1, 6)} or requirement_id in seen:
                return ok(False, "missing or duplicate requirement id")
            if (
                not isinstance(quote, str)
                or not quote
                or quote not in requirements
                or requirement_id not in quote
            ):
                return ok(False, "requirement evidence is not grounded")
            seen.add(requirement_id)
        if not (workspace / "reports/final_audit.md").is_file():
            return ok(False, "final audit missing")
        process = run(
            workspace,
            [
                "python",
                "tools/investigation_helper.py",
                "--audit",
                "reports/audit_matrix.json",
                "--output",
                str(eval_path(workspace, "lh3")),
            ],
        )
        return ok(
            process.returncode == 0 and seen == {f"R{index}" for index in range(1, 6)},
            "five grounded requirement rows and helper output verified",
        )

    return None
