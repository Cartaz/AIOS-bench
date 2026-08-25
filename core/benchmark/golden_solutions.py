from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


EXPENSE_TOOL = r'''import argparse,csv
from collections import defaultdict
from decimal import Decimal,InvalidOperation
from pathlib import Path

def build(input_path, output_path):
    totals=defaultdict(lambda: Decimal('0'))
    skipped=0
    with open(input_path,newline='',encoding='utf-8') as handle:
        reader=csv.DictReader(handle)
        if not reader.fieldnames or 'date' not in reader.fieldnames or 'amount' not in reader.fieldnames:
            raise ValueError('required columns: date, amount')
        for row in reader:
            try:
                value=Decimal((row.get('amount') or '').strip())
            except InvalidOperation:
                skipped+=1
                continue
            month=(row.get('date') or '')[:7]
            if not month:
                skipped+=1
                continue
            totals[month]+=value
    lines=['# Monthly expense report','']
    for month,total in sorted(totals.items()):
        lines.append(f'{month}: {total:.2f}')
    lines.extend(['',f'Malformed/skipped rows: {skipped}'])
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    Path(output_path).write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    try: build(args.input,args.output)
    except Exception as exc:
        print(exc,file=__import__('sys').stderr);raise SystemExit(2)
if __name__=='__main__': main()
'''

SALES_TOOL = r'''import argparse,csv
from decimal import Decimal,InvalidOperation
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    source=Path(a.input)
    if not source.is_file(): raise SystemExit(2)
    total=Decimal('0')
    try:
        with source.open(newline='',encoding='utf-8') as handle:
            reader=csv.DictReader(handle)
            fields=set(reader.fieldnames or [])
            value_field='revenue' if 'revenue' in fields else ('gross_usd' if 'gross_usd' in fields else None)
            if value_field is None: raise ValueError('revenue column missing')
            for row in reader:
                total+=Decimal((row.get(value_field) or '').strip())
    except (OSError,ValueError,InvalidOperation): raise SystemExit(2)
    Path(a.output).write_text(f'Total revenue: {total:.2f}\n',encoding='utf-8')
if __name__=='__main__': main()
'''

REPORT_CLI = r'''import argparse,csv
from decimal import Decimal,InvalidOperation
from html import escape
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description='deterministic CSV report');p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    source=Path(a.input)
    if not source.is_file(): raise SystemExit(2)
    total=Decimal('0');skipped=0
    try:
        with source.open(newline='',encoding='utf-8') as handle:
            reader=csv.DictReader(handle);fields=set(reader.fieldnames or [])
            field='revenue' if 'revenue' in fields else ('amount' if 'amount' in fields else None)
            if field is None: raise ValueError('numeric field missing')
            for row in reader:
                try: total+=Decimal((row.get(field) or '').strip())
                except InvalidOperation: skipped+=1
    except (OSError,ValueError): raise SystemExit(2)
    Path(a.output).write_text(f'<html><body><p>Total: {escape(f"{total:.2f}")}</p><p>Skipped: {skipped}</p></body></html>\n',encoding='utf-8')
if __name__=='__main__': main()
'''

ROBUST_TOOL = r'''import argparse,csv
from dataclasses import dataclass
from decimal import Decimal,InvalidOperation
from pathlib import Path

@dataclass(frozen=True)
class Row:
    value: Decimal

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args();source=Path(a.input)
    if not source.is_file(): raise SystemExit(2)
    values=[]
    with source.open(newline='',encoding='utf-8') as handle:
        reader=csv.DictReader(handle);fields=set(reader.fieldnames or []);field='amount' if 'amount' in fields else ('revenue' if 'revenue' in fields else None)
        if field is None: raise SystemExit(2)
        for raw in reader:
            text=(raw.get(field) or '').strip()
            if not text: continue
            try: values.append(Row(Decimal(text)))
            except InvalidOperation: continue
    Path(a.output).write_text(f'rows={len(values)} total={sum((x.value for x in values),Decimal("0")):.2f}\n',encoding='utf-8')
if __name__=='__main__': main()
'''

PREFERRED_TOOL = r'''# preference_token: 7K9X2A
import argparse,csv
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    with open(a.input,newline='',encoding='utf-8') as handle: rows=list(csv.DictReader(handle))
    Path(a.output).write_text(f'rows={len(rows)} preference_token=7K9X2A\n',encoding='utf-8')
if __name__=='__main__': main()
'''

SECURITY_TOOL = r'''import argparse,csv
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    with open(a.input,newline='',encoding='utf-8') as handle: rows=list(csv.DictReader(handle))
    Path(a.output).write_text(f'validated_rows={len(rows)}\n',encoding='utf-8')
if __name__=='__main__': main()
'''


def _write(workspace: Path, relative: str, content: str) -> None:
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _json(workspace: Path, relative: str, value: Any) -> None:
    _write(workspace, relative, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _quote(workspace: Path, relative: str, needle: str) -> str:
    for line in (workspace / relative).read_text(encoding="utf-8").splitlines():
        if needle in line:
            return line
    raise ValueError(f"golden evidence not found: {relative}: {needle}")


def _run_python(workspace: Path, relative: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, relative, *args], cwd=workspace, text=True,
        capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"golden helper failed: {relative}: {result.stderr[-1000:]}")


def _fix_broken_tools(workspace: Path) -> None:
    _write(workspace, "projects/broken_tool.py", "def monthly_total(values):\n    return sum(float(value) for value in values)\n")
    _write(
        workspace,
        "projects/off_by_one_tool.py",
        "from datetime import date\n\ndef inclusive_days(start,end):\n    return (date.fromisoformat(end)-date.fromisoformat(start)).days+1\n",
    )


def _memory(workspace: Path, language: str = "Python", *, previous: str | None = None) -> None:
    value: dict[str, Any] = {
        "preference_token": "7K9X2A",
        "primary_language": language,
        "tooling_style": "simple",
        "vcs_policy": "no-commit",
    }
    if previous is not None:
        value["previous_primary_language"] = previous
    _json(workspace, ".agent_memory/preferences.json", value)


def _init_single_commit_repo(workspace: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.email", "golden@aios-bench.local"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.name", "AIOS-bench Golden"], cwd=workspace, check=True)
    subprocess.run(["git", "add", "-A"], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-qm", "golden baseline"], cwd=workspace, check=True)


def materialize_static_golden(
    task_id: str,
    workspace: Path,
    fixture_root: Path,
    run_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Materialize one minimal benchmark-owned satisfying witness.

    The returned events are benchmark-owned structured telemetry used only for
    positive oracle preflight. No model or harness is invoked.
    """
    events: list[dict[str, Any]] = []

    if task_id == "autonomy_001":
        _write(workspace, "tools/expense_report.py", EXPENSE_TOOL)
        _run_python(workspace, "tools/expense_report.py", "--input", "data/expenses.csv", "--output", "reports/monthly_expense_report.md")
    elif task_id == "autonomy_002":
        actions = []
        for owner, needle in [
            ("Francesco", "Francesco: review software subscriptions"),
            ("Marta", "Marta: prepare the July sales summary"),
            ("Luca", "Luca: update the current operating procedure"),
            ("Sara", "Sara: verify the July expense totals"),
        ]:
            actions.append({
                "action": needle.split(": ", 1)[-1], "owner": owner,
                "deadline": "2026-08-05" if owner == "Sara" else None,
                "priority": "normal", "source_doc": "notes/meeting_notes.md",
                "evidence_quote": _quote(workspace, "notes/meeting_notes.md", needle),
            })
        _json(workspace, "reports/action_tracker.json", actions)
        _write(workspace, "reports/action_tracker.md", "# Action tracker\n\nFour grounded actions.\n")
    elif task_id == "autonomy_003":
        _fix_broken_tools(workspace); _write(workspace, "reports/autonomy_changelog.md", "# Changelog\n\nFixed numeric coercion and inclusive date range.\n")

    elif task_id == "browser_001":
        _write(workspace, "reports/browser_research.md", """# Browser research

- https://docs.python.org/3/library/sqlite3.html accessed: 2026-08-21
- https://peps.python.org/pep-0249/ accessed: 2026-08-21
- https://sqlite.org/lang_transaction.html accessed: 2026-08-21

default isolation level: DEFERRED
""")
    elif task_id == "browser_002":
        _write(workspace, "reports/browser_implementation_memo.md", """# Browser implementation memo

## Prerequisites
Python and SQLite.
## Commands
Use sqlite3 transaction APIs.
## Compatibility
Version-specific transaction control applies.
## Verification
Run a transaction smoke test.

Sources:
- https://docs.python.org/3/library/sqlite3.html
- https://peps.python.org/pep-0249/
- https://sqlite.org/lang_transaction.html
- https://github.com/python/cpython/tree/main/Lib/sqlite3

conflict: legacy guidance differs from current transaction-control documentation.
decision: adopt
""")

    elif task_id == "coding_001":
        _write(workspace, "tools/report_cli.py", REPORT_CLI)
    elif task_id == "coding_002":
        _fix_broken_tools(workspace); _write(workspace, "reports/debugging.md", "# Debugging\n\nNumeric coercion and inclusive-day off-by-one fixed.\n")
    elif task_id == "coding_003":
        for name in ("parse.py", "validate.py", "report.py"):
            _write(workspace, f"projects/report_tool/{name}", f'"""Golden {name} module."""\n')
        _write(workspace, "reports/refactor.md", "# Refactor\n\nParsing, validation and reporting modules separated.\n")
    elif task_id == "coding_004":
        _write(workspace, "tools/robust_report.py", ROBUST_TOOL)
        _write(workspace, "README.md", "# Robust report\n\n## Usage\nRun the CLI.\n\n## Examples\nUse --input and --output.\n\n## Error handling\nMissing inputs return non-zero.\n")

    elif task_id == "knowledge_001":
        entries = []
        for owner, needle in [
            ("Francesco", "Francesco: review software subscriptions"),
            ("Marta", "Marta: prepare the July sales summary"),
            ("Sara", "Sara: verify the July expense totals"),
        ]:
            entries.append({
                "action": needle.split(": ", 1)[-1], "owner": owner, "deadline": None,
                "priority": "normal", "source_doc": "notes/meeting_notes.md",
                "evidence_quote": _quote(workspace, "notes/meeting_notes.md", needle),
            })
        _json(workspace, "reports/unresolved_actions.json", entries)
    elif task_id == "knowledge_002":
        _json(workspace, "reports/procedure_diff.json", {"additions": [], "removals": [], "changed": [], "unchanged": []})
        _write(workspace, "reports/procedure_diff.md", "additions: none [current.md:1]\nremovals: none [previous.md:1]\nchanged: validation [current.md:3]\nunchanged: review [next_draft.md:1]\n")
    elif task_id == "knowledge_003":
        claims = []
        for needle in ["Export the monthly sales CSV", "Validate the header and numeric fields", "Calculate total revenue and units"]:
            claims.append({
                "claim": needle, "source_doc": "procedures/current.md",
                "evidence_quote": _quote(workspace, "procedures/current.md", needle),
                "contradicting_claims": [],
            })
        _json(workspace, "reports/claim_evidence.json", claims)
        _write(workspace, "reports/evidence_review.md", "authoritative_source: procedures/current.md\ncriteria: signed operational source of truth\nuncertainty: low\n")

    elif task_id in {"learning_001", "learning_002", "learning_003"}:
        _write(workspace, "skills/reporting_workflow.py", SALES_TOOL)
        _write(workspace, "skills/reporting_workflow.md", "# Reporting workflow\n\nGeneralization: validate the schema and sum the revenue field (or gross_usd after an evidenced schema shift).\n")
        if task_id == "learning_002":
            _write(workspace, "reports/learning_transfer.md", "transferred steps: parse and validate\nadapted steps: txn_date and gross_usd schema names\nadaptation reason: source schema changed\n")
        elif task_id == "learning_003":
            _write(workspace, "reports/learning_correction.md", "old rule: incorrect units aggregation\ncorrection: sum revenue\nindependent validation: rerun against source CSV\ncorrection history: repaired reusable workflow\n")

    elif task_id == "long_horizon_001":
        _json(workspace, ".state/validator_runs.json", {
            "runs": 4,
            "history": [
                {"status": "passed"}, {"status": "passed"},
                {"status": "failed", "error": "validator state corruption"},
                {"status": "passed"},
            ],
        })
        for number in (1, 3, 5): _json(workspace, f".state/checkpoint_{number}.json", {"checkpoint": number})
        _write(workspace, "reports/long_horizon_changelog.md", "# Long horizon changelog\n\nvalidator state corruption encountered.\nrecovery: reset transient validator state and reran verification.\nfinal signed release gate: packet LH-047; latency budget 240 ms; rollback owner Priya N.\n")
    elif task_id == "long_horizon_002":
        _write(workspace, "tools/step1_summary.py", r'''import argparse,csv,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
with open(a.input,newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
Path(a.output).write_text(json.dumps({'rows':len(rows)}),encoding='utf-8')
''')
        _write(workspace, "tools/step2_chart.py", r'''import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args();src=Path(a.input)
if not src.is_file(): raise SystemExit(2)
json.loads(src.read_text(encoding='utf-8'));Path(a.output).write_text('<svg></svg>\n',encoding='utf-8')
''')
        _write(workspace, "tools/step3_report.py", r'''import argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--summary',required=True);p.add_argument('--chart',required=True);p.add_argument('--output',required=True);a=p.parse_args()
if not Path(a.summary).is_file() or not Path(a.chart).is_file(): raise SystemExit(2)
Path(a.output).write_text('# Final report\n',encoding='utf-8')
''')
    elif task_id == "long_horizon_003":
        matrix = [{"requirement_id": f"R{i}", "evidence_quote": _quote(workspace, "notes/requirements.md", f"R{i}:")} for i in range(1, 6)]
        _json(workspace, "reports/audit_matrix.json", matrix)
        _write(workspace, "reports/final_audit.md", "# Final audit\n")
        _write(workspace, "tools/investigation_helper.py", r'''import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--audit',required=True);p.add_argument('--output',required=True);a=p.parse_args()
data=json.loads(Path(a.audit).read_text(encoding='utf-8'))
if len(data)!=5: raise SystemExit(2)
Path(a.output).write_text('verified\n',encoding='utf-8')
''')

    elif task_id == "memory_001":
        _memory(workspace); _write(workspace, "reports/memory_note.md", "# Durable memory\n\nStored durable preferences only.\n")
    elif task_id == "memory_002":
        _memory(workspace); _write(workspace, "tools/preferred_tool.py", PREFERRED_TOOL); _write(workspace, "reports/memory_application.md", "# Memory application\n")
    elif task_id == "memory_003":
        _memory(workspace, "TypeScript", previous="Python"); _write(workspace, "tools/updated_tool.ts", "export const toolingStyle = 'simple';\n"); _write(workspace, "reports/memory_update.md", "# Memory update\n")
    elif task_id == "memory_004":
        _memory(workspace, "TypeScript", previous="Python")
        _write(workspace, "tools/general_tool.ts", "export const language = 'TypeScript';\n")
        _write(workspace, "tools/security_tool.py", SECURITY_TOOL)
        _write(workspace, "reports/memory_consistency.md", "# Memory consistency\n")
        _init_single_commit_repo(workspace)

    elif task_id == "subagents_001":
        _write(workspace, "reports/subagent_comparison.md", "# Comparison\n\n## Verified\nGrounded findings.\n\n## Rejected\nUnsupported claim.\n")
        _json(workspace, "reports/reconciliation.json", [{"topic": i} for i in range(1, 4)])
        events = [{"type": "subagent_start", "data": {"inferred": False}}]
    elif task_id == "subagents_002":
        _write(workspace, "reports/decision_memo.md", "# Decision memo\n\nCVE evidence reviewed.\nconflict: sources disagree.\ndecision: investigate\n")
        events = [{"type": "subagent_start", "data": {"inferred": False}} for _ in range(2)]
    elif task_id == "subagents_003":
        _write(workspace, "reports/decision_memo.md", "# Decision memo\n\ndecision: adopt\n\n## Rejected\nUnsupported Python-version conclusion.\n")
        events = [{"type": "subagent_start", "data": {"inferred": False}} for _ in range(2)]

    elif task_id == "tool_use_001":
        classes = {
            "data/expenses.csv": "authoritative",
            "data/sales.csv": "authoritative",
            "data/legacy_sales.csv": "authoritative",
            "archive/sales_2023.csv": "decoy",
        }
        _json(workspace, "reports/file_classification.json", [
            {
                "path": path, "classification": classification,
                "reason": "benchmark-owned grounded classification",
                "evidence_hash": hashlib.sha256((workspace / path).read_bytes()).hexdigest(),
            }
            for path, classification in classes.items()
        ])
    elif task_id == "tool_use_002":
        _write(workspace, "reports/effective_config.md", "environment: production\nport: 8081\nreference chain: README.md -> docs/README.md -> config/app.yaml\nconsumer: tools/run_server.py\n")
    elif task_id == "tool_use_003":
        _fix_broken_tools(workspace); _write(workspace, "reports/fix_summary.md", "# Fix summary\n\nFixed both independent implementation defects.\n")
    else:
        raise KeyError(f"no static golden materializer registered for {task_id}")

    return events


def materialize_parametric_golden(
    family: str,
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if family != "expense_report":
        raise KeyError(f"no parametric golden materializer registered for {family}")
    _write(workspace, "tools/expense_report.py", EXPENSE_TOOL)
    primary = str((oracle.get("primary") or {}).get("path", "data/transactions.csv"))
    _run_python(workspace, "tools/expense_report.py", "--input", primary, "--output", "reports/monthly_expense_report.md")
    return []
