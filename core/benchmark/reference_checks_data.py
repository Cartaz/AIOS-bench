from __future__ import annotations

import json
import re
from pathlib import Path

from .reference_checks_core import CheckResult, eval_path, load, ok, read, run, same

_STOPWORDS = {"the", "and", "for", "from", "with", "this", "that", "into", "only", "when", "then"}


def _terms(value: object) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_.-]+", str(value).lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _aligned(claim: object, evidence: object) -> bool:
    claim_terms = _terms(claim)
    evidence_terms = _terms(evidence)
    if not claim_terms or not evidence_terms:
        return False
    overlap = claim_terms & evidence_terms
    return len(overlap) >= 2 and len(overlap) / len(claim_terms) >= 0.4


def check(task_id: str, workspace: Path, fixture_root: Path) -> CheckResult:
    if task_id == "autonomy_001":
        first = eval_path(workspace, "a1.md")
        alternate = eval_path(workspace, "a1a.md")
        first_run = run(
            workspace,
            [
                "python",
                "tools/expense_report.py",
                "--input",
                "data/expenses.csv",
                "--output",
                str(first),
            ],
        )
        alternate_run = run(
            workspace,
            [
                "python",
                "tools/expense_report.py",
                "--input",
                "data/expenses_alt.csv",
                "--output",
                str(alternate),
            ],
        )
        if first_run.returncode or alternate_run.returncode:
            return ok(False, "expense tool failed")
        first_text = first.read_text(errors="replace")
        alternate_text = alternate.read_text(errors="replace")
        good = (
            "91.07" in first_text
            and "742.50" in alternate_text
            and re.search(r"(skipped|malformed).{0,30}1", first_text, re.I | re.S)
            and "91.07" not in read(workspace, "tools/expense_report.py")
        )
        return ok(good, "expense tool executes on both datasets")

    if task_id == "autonomy_002":
        actions = load(workspace, "reports/action_tracker.json")
        if not isinstance(actions, list) or len(actions) != 4:
            return ok(False, "expected four actions")
        seen: set[str] = set()
        for entry in actions:
            if not isinstance(entry, dict):
                return ok(False, "invalid action entry")
            source = workspace / str(entry.get("source_doc", ""))
            evidence = entry.get("evidence_quote", "")
            action = entry.get("action", "")
            if (
                not source.is_file()
                or not evidence
                or evidence not in source.read_text(encoding="utf-8")
                or not _aligned(action, evidence)
            ):
                return ok(False, "fabricated or misaligned evidence")
            key = re.sub(r"\W+", " ", str(action).lower()).strip()
            if not key or key in seen:
                return ok(False, "duplicate or empty action")
            seen.add(key)
        return ok(
            not any("Q3 budget" in json.dumps(entry) for entry in actions),
            "grounded action tracker",
        )

    if task_id in {"autonomy_003", "coding_002", "tool_use_003"}:
        protected = [
            "tests/test_broken_tool.py",
            "tests/test_off_by_one.py",
            "data/expenses.csv",
            "data/sales.csv",
            "notes/meeting_notes.md",
            "procedures/current.md",
            "procedures/previous.md",
        ]
        for relative_path in protected:
            if not same(workspace, relative_path, fixture_root):
                return ok(False, f"protected file modified: {relative_path}")
        tests = run(
            workspace,
            [
                "python",
                "-m",
                "pytest",
                "-q",
                "tests/test_broken_tool.py",
                "tests/test_off_by_one.py",
            ],
            45,
        )
        return ok(tests.returncode == 0, "hidden regression tests pass")

    if task_id == "coding_001":
        if not same(workspace, "tests/test_hidden_report_cli.py", fixture_root):
            return ok(False, "hidden test modified")
        tests = run(
            workspace,
            ["python", "-m", "pytest", "-q", "tests/test_hidden_report_cli.py"],
            45,
        )
        return ok(tests.returncode == 0, "hidden CLI tests pass")

    if task_id == "coding_003":
        required = [
            "projects/report_tool/parse.py",
            "projects/report_tool/validate.py",
            "projects/report_tool/report.py",
        ]
        if not all((workspace / path).is_file() for path in required) or not same(
            workspace,
            "tests/test_cli_contract.py",
            fixture_root,
        ):
            return ok(False, "refactor contract incomplete")
        tests = run(
            workspace,
            ["python", "-m", "pytest", "-q", "tests/test_cli_contract.py"],
            45,
        )
        return ok(tests.returncode == 0, "CLI contract preserved")

    if task_id == "coding_004":
        if not same(workspace, "tests/test_robust.py", fixture_root):
            return ok(False, "hidden robustness test modified")
        tests = run(
            workspace,
            ["python", "-m", "pytest", "-q", "tests/test_robust.py"],
            45,
        )
        tool = read(workspace, "tools/robust_report.py")
        readme = read(workspace, "README.md")
        good = (
            tests.returncode == 0
            and re.search(r"@dataclass|TypedDict|class\s+\w+\s*\(", tool) is not None
            and all(
                re.search(rf"^#+\s+{section}\b", readme, re.I | re.M)
                for section in ["Usage", "Examples", "Error handling"]
            )
        )
        return ok(good, "robust utility verified")

    if task_id == "learning_001":
        workflow = read(workspace, "skills/reporting_workflow.md")
        if "580" in workflow or "91.07" in workflow:
            return ok(False, "workflow hard-codes fixture totals")
        first = eval_path(workspace, "l1")
        alternate = eval_path(workspace, "l1a")
        first_run = run(
            workspace,
            [
                "python",
                "skills/reporting_workflow.py",
                "--input",
                "data/sales.csv",
                "--output",
                str(first),
            ],
        )
        alternate_run = run(
            workspace,
            [
                "python",
                "skills/reporting_workflow.py",
                "--input",
                "data/sales_alt.csv",
                "--output",
                str(alternate),
            ],
        )
        good = (
            first_run.returncode == alternate_run.returncode == 0
            and "580" in first.read_text(errors="replace")
            and "742" in alternate.read_text(errors="replace")
            and re.search(r"generalization\s*:", workflow, re.I)
        )
        return ok(bool(good), "learned workflow transfers")

    if task_id == "learning_002":
        report = read(workspace, "reports/learning_transfer.md")
        output = eval_path(workspace, "l2")
        process = run(
            workspace,
            [
                "python",
                "skills/reporting_workflow.py",
                "--input",
                "data/sales_schema_shift.csv",
                "--output",
                str(output),
            ],
        )
        rendered = output.read_text(errors="replace") if output.exists() else ""
        patterns = [
            r"transferred\s+steps\s*:",
            r"adapted\s+steps\s*:",
            r"adaptation\s+reason\s*:",
            r"txn_date|gross_usd",
        ]
        good = (
            process.returncode == 0
            and "580" in rendered
            and all(re.search(pattern, report, re.I) for pattern in patterns)
        )
        return ok(good, "learning transfer verified on shifted-schema outcome")

    if task_id == "learning_003":
        workflow = read(workspace, "skills/reporting_workflow.md")
        report = read(workspace, "reports/learning_correction.md")
        output = eval_path(workspace, "l3")
        process = run(
            workspace,
            [
                "python",
                "skills/reporting_workflow.py",
                "--input",
                "data/sales.csv",
                "--output",
                str(output),
            ],
        )
        rendered = output.read_text(errors="replace") if output.exists() else ""
        good = (
            "sum of the `units`" not in workflow
            and re.search(r"sum.*revenue", workflow, re.I)
            and re.search(r"independent\s+validation\s*:\s*\S+", report, re.I)
            and process.returncode == 0
            and "580" in rendered
        )
        return ok(bool(good), "planted learning error corrected")

    return None
