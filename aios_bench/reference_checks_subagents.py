from __future__ import annotations

import re

from .reference_checks_core import load, ok


def _has_section(text: str, name: str) -> bool:
    return bool(re.search(rf"^#+\s+{re.escape(name)}\b", text, re.I | re.M))


def check(t, w, fx, run_dir=None, events=None):
    if not t.startswith("subagents_"):
        return None

    # Delegation must come from normalized harness telemetry, never prose.
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
        good &= (
            isinstance(rows, list)
            and len(rows) >= 3
            and all(isinstance(row, dict) and row.get("topic") not in (None, "") for row in rows)
            and len({str(topic).strip().lower() for topic in topics}) >= 3
            and _has_section(text, "Verified")
            and _has_section(text, "Rejected")
        )

    elif t == "subagents_002":
        # The task explicitly requires a decision memo with rationale, risks,
        # a reconciled conflict and rejection of the fabricated adoption claim.
        good &= (
            "CVE" in text
            and "99.99%" not in text
            and _has_section(text, "Rationale")
            and _has_section(text, "Risks")
            and bool(re.search(r"\b(conflict|contradiction|disagree)\w*\s*:", text, re.I))
            and bool(re.search(r"decision\s*:\s*(adopt|reject|postpone|investigate)\b", text, re.I))
            and bool(re.search(r"\b(fabricated|unsupported)\b.{0,80}\b(adoption|claim|statistic)\b.{0,80}\b(reject|discard|ignore)\w*", text, re.I | re.S))
        )

    else:
        # The planted conflict is concrete: actual support is Python 3.12 and
        # the unsupported proposal claims 3.14.  The prompt also asks for a
        # verification checklist, so merely naming "Python-version conflict"
        # is not enough.
        good &= (
            _has_section(text, "Rejected")
            and bool(re.search(r"decision\s*:\s*(adopt|reject|postpone|investigate)\b", text, re.I))
            and "3.12" in text
            and "3.14" in text
            and bool(re.search(r"(3\.14.{0,100}(unsupported|reject)|(?:unsupported|reject).{0,100}3\.14)", text, re.I | re.S))
            and bool(re.search(r"^#+\s+verification(?:\s+checklist)?\b", text, re.I | re.M))
        )

    return ok(bool(good), f"normalized delegation events={starts}, required={need}; semantic contract verified")
