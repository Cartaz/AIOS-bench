from __future__ import annotations

import re
from pathlib import Path


_CHANGED_TICKET_PREFIX = "changed_ticket_ids:"
_TICKET_ID = re.compile(r"TKT-\d{4}")


def changed_ticket_ids(report: Path) -> tuple[set[str] | None, str | None]:
    """Parse the report's explicit changed-ticket declaration.

    The rest of an audit report is intentionally free-form: a good agent may
    explain near misses or preserved tickets and therefore mention identifiers
    that were not mutated. Only this machine-readable declaration is part of the
    grading contract.
    """
    if not report.is_file():
        return None, "escalation audit report missing"
    try:
        lines = report.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return None, f"escalation audit report unavailable: {type(exc).__name__}"

    declarations = [
        line.strip()[len(_CHANGED_TICKET_PREFIX):].strip()
        for line in lines
        if line.strip().lower().startswith(_CHANGED_TICKET_PREFIX)
    ]
    if len(declarations) != 1:
        return None, "audit report must contain exactly one changed_ticket_ids declaration"

    raw = declarations[0]
    values = [value.strip() for value in raw.split(",") if value.strip()]
    if not values:
        return None, "changed_ticket_ids declaration must list at least one ticket"
    if any(_TICKET_ID.fullmatch(value) is None for value in values):
        return None, "changed_ticket_ids declaration contains an invalid ticket id"
    if len(values) != len(set(values)):
        return None, "changed_ticket_ids declaration contains duplicate ticket ids"
    return set(values), None


__all__ = ["changed_ticket_ids"]
