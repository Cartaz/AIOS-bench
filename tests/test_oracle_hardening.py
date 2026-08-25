import json
import shutil
from pathlib import Path

from aios_bench.reference_checks_knowledge import check


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks" / "fixtures" / "workspace"


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURE, workspace)
    (workspace / "reports").mkdir(exist_ok=True)
    return workspace


def test_knowledge_002_rejects_structural_filler_without_semantic_core(tmp_path: Path):
    workspace = _workspace(tmp_path)
    (workspace / "reports/procedure_diff.json").write_text(
        json.dumps({"additions": [], "removals": [], "changed": [], "unchanged": []}),
        encoding="utf-8",
    )
    (workspace / "reports/procedure_diff.md").write_text(
        "additions: none [current.md:1]\n"
        "removals: none [previous.md:1]\n"
        "changed: generic update [current.md:1]\n"
        "unchanged: generic workflow [next_draft.md:1]\n",
        encoding="utf-8",
    )

    passed, detail = check("knowledge_002", workspace, FIXTURE)

    assert passed is False
    assert "semantic core" in detail


def test_knowledge_002_rejects_fake_or_out_of_range_provenance(tmp_path: Path):
    workspace = _workspace(tmp_path)
    (workspace / "reports/procedure_diff.json").write_text(
        json.dumps({"additions": [], "removals": [], "changed": [], "unchanged": []}),
        encoding="utf-8",
    )
    (workspace / "reports/procedure_diff.md").write_text(
        "additions: validation [current.md:999]\n"
        "removals: review [previous.md:999]\n"
        "changed: validation [current.md:999]\n"
        "unchanged: review [next_draft.md:999]\n",
        encoding="utf-8",
    )

    passed, _ = check("knowledge_002", workspace, FIXTURE)

    assert passed is False


def test_knowledge_003_rejects_real_quote_attached_to_unrelated_claim(tmp_path: Path):
    workspace = _workspace(tmp_path)
    claims = [
        {
            "claim": "The moon is made of parmesan",
            "source_doc": "procedures/current.md",
            "evidence_quote": "1. Export the monthly sales CSV.",
            "contradicting_claims": [],
        },
        {
            "claim": "Validate the header and numeric fields",
            "source_doc": "procedures/current.md",
            "evidence_quote": "2. Validate the header and numeric fields.",
            "contradicting_claims": [],
        },
        {
            "claim": "Calculate total revenue and units",
            "source_doc": "procedures/current.md",
            "evidence_quote": "3. Calculate total revenue and units.",
            "contradicting_claims": [],
        },
    ]
    (workspace / "reports/claim_evidence.json").write_text(
        json.dumps(claims), encoding="utf-8"
    )
    (workspace / "reports/evidence_review.md").write_text(
        "authoritative_source: procedures/current.md\n"
        "criteria: signed operational source of truth\n"
        "uncertainty: low\n",
        encoding="utf-8",
    )

    passed, detail = check("knowledge_003", workspace, FIXTURE)

    assert passed is False
    assert "semantic alignment" in detail


def test_knowledge_003_rejects_missing_required_workflow_core(tmp_path: Path):
    workspace = _workspace(tmp_path)
    claims = [
        {
            "claim": "Export the monthly sales CSV",
            "source_doc": "procedures/current.md",
            "evidence_quote": "1. Export the monthly sales CSV.",
            "contradicting_claims": [],
        },
        {
            "claim": "Save the summary as reports/monthly-sales.md",
            "source_doc": "procedures/current.md",
            "evidence_quote": "4. Save the summary as `reports/monthly-sales.md`.",
            "contradicting_claims": [],
        },
        {
            "claim": "Review the result before sharing it",
            "source_doc": "procedures/current.md",
            "evidence_quote": "5. Review the result before sharing it.",
            "contradicting_claims": [],
        },
    ]
    (workspace / "reports/claim_evidence.json").write_text(
        json.dumps(claims), encoding="utf-8"
    )
    (workspace / "reports/evidence_review.md").write_text(
        "authoritative_source: procedures/current.md\n"
        "criteria: signed operational source of truth\n"
        "uncertainty: low\n",
        encoding="utf-8",
    )

    passed, _ = check("knowledge_003", workspace, FIXTURE)

    assert passed is False
