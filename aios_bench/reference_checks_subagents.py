from __future__ import annotations

import re

from .reference_checks_core import load, ok


def _has_section(text: str, name: str) -> bool:
    return bool(re.search(rf"^#+\s+{re.escape(name)}\b|^\s*{re.escape(name)}\s*:", text, re.I | re.M))


def check(t, w, fx, run_dir=None, events=None):
    if not t.startswith("subagents_"):
        return None

    starts = sum(
        event.get("type") == "subagent_start"
        and not (event.get("data") or {}).get("inferred", False)
        for event in (events or [])
    )
    need = 1 if t == "subagents_001" else 2
    report = w / ("reports/subagent_comparison.md" if t == "subagents_001" else "reports/decision_memo.md")
    if not report.is_file():
        return ok(False, "decision report missing")
    text = report.read_text(encoding="utf-8", errors="replace")
    good = starts >= need

    if t == "subagents_001":
        reconciliation = w / "reports/reconciliation.json"
        if not reconciliation.is_file():
            return ok(False, "reconciliation missing")
        rows = load(w, "reports/reconciliation.json")
        topics = [row.get("topic") for row in rows] if isinstance(rows, list) else []
        grounded_rows = (
            isinstance(rows, list)
            and len(rows) >= 3
            and all(isinstance(row, dict) and isinstance(row.get("topic"), str) and row["topic"].strip() for row in rows)
            and len({topic.strip().lower() for topic in topics}) >= 3
        )
        good &= (
            grounded_rows
            and _has_section(text, "Verified")
            and _has_section(text, "Rejected")
            and bool(re.search(r"\b(conflict|contradiction|disagree)\w*\b", text, re.I))
        )

    elif t == "subagents_002":
        rejected_stat = bool(
            re.search(r"reject\w*.{0,80}99\.99%|99\.99%.{0,80}reject\w*", text, re.I | re.S)
        )
        good &= (
            _has_section(text, "Decision")
            and _has_section(text, "Rationale")
            and _has_section(text, "Risks")
            and "CVE-2024-XXXX" in text
            and bool(re.search(r"\b(conflict|contradiction|disagree)\w*\b", text, re.I))
            and rejected_stat
            and "rollback" in text.lower()
        )

    else:
        decision = bool(re.search(r"decision\s*:\s*(adopt|reject|postpone|investigate)\b", text, re.I))
        rejected_py314 = bool(
            re.search(r"reject\w*.{0,120}3\.14|3\.14.{0,120}(unsupported|reject\w*)", text, re.I | re.S)
        )
        good &= (
            decision
            and _has_section(text, "Rejected")
            and "3.12" in text
            and "3.14" in text
            and rejected_py314
            and bool(re.search(r"^#+\s+(verification\s+)?checklist\b", text, re.I | re.M))
        )

    return ok(bool(good), f"normalized delegation events={starts}, required={need}; semantic contract verified")
