from __future__ import annotations

import json
from pathlib import Path


def _write(workspace: Path, relative: str, content: str) -> None:
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _json(workspace: Path, relative: str, value: object) -> None:
    _write(workspace, relative, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def finalize_static_golden(task_id: str, workspace: Path) -> None:
    """Complete benchmark-owned golden witnesses for stricter semantic oracles.

    This runs only during benchmark self-validation. It does not affect agent
    workspaces or benchmark runtime.
    """
    if task_id == "knowledge_002":
        _json(
            workspace,
            "reports/procedure_diff.json",
            {
                "additions": [
                    {"change": "Validate the header and numeric fields", "operator_impact": "validation is now mandatory"},
                    {"change": "Review the result before sharing it", "operator_impact": "a review gate is now required"},
                ],
                "removals": [
                    {"change": "Send the summary without a separate review step", "operator_impact": "direct sharing is no longer allowed"}
                ],
                "changed": [
                    {"change": "Calculate total revenue and units instead of revenue only", "operator_impact": "units must also be calculated"},
                    {"change": "Write reports/monthly-sales.md instead of reports/monthly-sales.txt", "operator_impact": "the output format/path changed"},
                    {"change": "The next draft replaces review-before-sharing with the project PR workflow", "operator_impact": "draft publication would move through a pull request"},
                ],
                "unchanged": [
                    {"change": "Export the monthly sales CSV", "operator_impact": "no operator change"}
                ],
            },
        )
        _write(
            workspace,
            "reports/procedure_diff.md",
            """# Procedure diff

additions: validate the header and numeric fields [current.md:4]; review the result before sharing it [current.md:7]
removals: send the summary without a separate review step [previous.md:6]
changed: calculate total revenue and units [current.md:5]; output reports/monthly-sales.md instead of reports/monthly-sales.txt [current.md:6] [previous.md:5]; the next draft uses the project PR workflow / pull request instead of the current review-before-sharing step [next_draft.md:7]
unchanged: export the monthly sales CSV [previous.md:3] [current.md:3] [next_draft.md:3]
operator impact: validation and review become mandatory, the report format changes, units are added, and the draft PR workflow would alter publication.
""",
        )

    elif task_id == "knowledge_003":
        claims = [
            {
                "claim": "Export the monthly sales CSV",
                "source_doc": "procedures/current.md",
                "evidence_quote": "1. Export the monthly sales CSV.",
                "contradicting_claims": [],
            },
            {
                "claim": "Validate the header and numeric fields",
                "source_doc": "procedures/current.md",
                "evidence_quote": "2. Validate the header and numeric fields.",
                "contradicting_claims": ["The previous procedure had no validation step."],
            },
            {
                "claim": "Calculate total revenue and units",
                "source_doc": "procedures/current.md",
                "evidence_quote": "3. Calculate total revenue and units.",
                "contradicting_claims": ["The previous procedure calculated total revenue only."],
            },
            {
                "claim": "Save the summary as reports/monthly-sales.md",
                "source_doc": "procedures/current.md",
                "evidence_quote": "4. Save the summary as `reports/monthly-sales.md`.",
                "contradicting_claims": ["The previous procedure used reports/monthly-sales.txt."],
            },
            {
                "claim": "Review the result before sharing it",
                "source_doc": "procedures/current.md",
                "evidence_quote": "5. Review the result before sharing it.",
                "contradicting_claims": [
                    "The previous procedure sends without a separate review step.",
                    "The next draft uses the project PR workflow instead.",
                ],
            },
        ]
        _json(workspace, "reports/claim_evidence.json", claims)
        _write(
            workspace,
            "reports/evidence_review.md",
            "authoritative_source: procedures/current.md\ncriteria: signed operational source of truth\nuncertainty: low\n",
        )
