from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .reference_checks_core import CheckResult, load, ok


def _has_section(text: str, name: str) -> bool:
    return bool(re.search(rf"^#+\s+{re.escape(name)}\b", text, re.I | re.M))


def check(
    task_id: str,
    workspace: Path,
    fixture_root: Path,
    run_dir: Path | None = None,
    events: list[dict[str, Any]] | None = None,
) -> CheckResult:
    del fixture_root, run_dir
    if not task_id.startswith("subagents_"):
        return None

    starts = sum(
        event.get("type") == "subagent_start"
        and not (event.get("data") or {}).get("inferred", False)
        for event in (events or [])
    )
    required_starts = 1 if task_id == "subagents_001" else 2
    report = workspace / (
        "reports/subagent_comparison.md"
        if task_id == "subagents_001"
        else "reports/decision_memo.md"
    )
    if not report.is_file():
        return ok(False, "decision report missing")
    text = report.read_text(encoding="utf-8", errors="replace")
    good = starts >= required_starts

    if task_id == "subagents_001":
        reconciliation = workspace / "reports/reconciliation.json"
        if not reconciliation.is_file():
            return ok(False, "reconciliation missing")
        rows = load(workspace, "reports/reconciliation.json")
        topics = [row.get("topic") for row in rows] if isinstance(rows, list) else []
        good &= (
            isinstance(rows, list)
            and len(rows) >= 3
            and all(
                isinstance(row, dict) and row.get("topic") not in (None, "")
                for row in rows
            )
            and len({str(topic).strip().lower() for topic in topics}) >= 3
            and _has_section(text, "Verified")
            and _has_section(text, "Rejected")
        )
    elif task_id == "subagents_002":
        good &= (
            "CVE" in text
            and "99.99%" not in text
            and bool(re.search(r"\b(conflict|contradiction|disagree)\w*\s*:", text, re.I))
            and bool(re.search(r"decision\s*:\s*(adopt|reject|postpone|investigate)\b", text, re.I))
        )
    else:
        good &= (
            _has_section(text, "Rejected")
            and bool(re.search(r"decision\s*:\s*(adopt|reject|postpone|investigate)\b", text, re.I))
            and bool(
                re.search(
                    r"unsupported.{0,40}python[- ]version|python[- ]version.{0,40}unsupported",
                    text,
                    re.I | re.S,
                )
            )
        )

    return ok(
        bool(good),
        f"normalized delegation events={starts}, required={required_starts}; semantic contract verified",
    )
