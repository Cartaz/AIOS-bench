import json
import shutil
from pathlib import Path

from aios_bench.reference_checks_data import check as check_data
from aios_bench.reference_checks_knowledge import check as check_knowledge
from aios_bench.reference_checks_long import check as check_long


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks" / "fixtures" / "workspace"


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURE, workspace)
    (workspace / "reports").mkdir(exist_ok=True)
    return workspace


def test_knowledge_002_rejects_structural_filler_without_semantic_core(tmp_path: Path):
    workspace = _workspace(tmp_path)
    (workspace / "reports/procedure_diff.json").write_text(json.dumps({"additions": [], "removals": [], "changed": [], "unchanged": []}), encoding="utf-8")
    (workspace / "reports/procedure_diff.md").write_text("additions: none [current.md:1]\nremovals: none [previous.md:1]\nchanged: generic update [current.md:1]\nunchanged: generic workflow [next_draft.md:1]\n", encoding="utf-8")
    passed, detail = check_knowledge("knowledge_002", workspace, FIXTURE)
    assert passed is False
    assert "semantic core" in detail


def test_knowledge_002_rejects_fake_or_out_of_range_provenance(tmp_path: Path):
    workspace = _workspace(tmp_path)
    (workspace / "reports/procedure_diff.json").write_text(json.dumps({"additions": [], "removals": [], "changed": [], "unchanged": []}), encoding="utf-8")
    (workspace / "reports/procedure_diff.md").write_text("additions: validation [current.md:999]\nremovals: review [previous.md:999]\nchanged: validation [current.md:999]\nunchanged: review [next_draft.md:999]\n", encoding="utf-8")
    passed, _ = check_knowledge("knowledge_002", workspace, FIXTURE)
    assert passed is False


def test_knowledge_003_rejects_real_quote_attached_to_unrelated_claim(tmp_path: Path):
    workspace = _workspace(tmp_path)
    claims = [
        {"claim": "The moon is made of parmesan", "source_doc": "procedures/current.md", "evidence_quote": "1. Export the monthly sales CSV.", "contradicting_claims": []},
        {"claim": "Validate the header and numeric fields", "source_doc": "procedures/current.md", "evidence_quote": "2. Validate the header and numeric fields.", "contradicting_claims": []},
        {"claim": "Calculate total revenue and units", "source_doc": "procedures/current.md", "evidence_quote": "3. Calculate total revenue and units.", "contradicting_claims": []},
    ]
    (workspace / "reports/claim_evidence.json").write_text(json.dumps(claims), encoding="utf-8")
    (workspace / "reports/evidence_review.md").write_text("authoritative_source: procedures/current.md\ncriteria: signed operational source of truth\nuncertainty: low\n", encoding="utf-8")
    passed, detail = check_knowledge("knowledge_003", workspace, FIXTURE)
    assert passed is False
    assert "semantic alignment" in detail


def test_knowledge_003_rejects_missing_required_workflow_core(tmp_path: Path):
    workspace = _workspace(tmp_path)
    claims = [
        {"claim": "Export the monthly sales CSV", "source_doc": "procedures/current.md", "evidence_quote": "1. Export the monthly sales CSV.", "contradicting_claims": []},
        {"claim": "Save the summary as reports/monthly-sales.md", "source_doc": "procedures/current.md", "evidence_quote": "4. Save the summary as `reports/monthly-sales.md`.", "contradicting_claims": []},
        {"claim": "Review the result before sharing it", "source_doc": "procedures/current.md", "evidence_quote": "5. Review the result before sharing it.", "contradicting_claims": []},
    ]
    (workspace / "reports/claim_evidence.json").write_text(json.dumps(claims), encoding="utf-8")
    (workspace / "reports/evidence_review.md").write_text("authoritative_source: procedures/current.md\ncriteria: signed operational source of truth\nuncertainty: low\n", encoding="utf-8")
    passed, _ = check_knowledge("knowledge_003", workspace, FIXTURE)
    assert passed is False


def test_knowledge_001_rejects_unrelated_action_with_real_quote(tmp_path: Path):
    workspace = _workspace(tmp_path)
    quote = "Francesco: review software subscriptions"
    entries = [
        {"action": "Launch a rocket to Mars", "source_doc": "notes/meeting_notes.md", "evidence_quote": quote},
        {"action": "prepare the July sales summary", "source_doc": "notes/meeting_notes.md", "evidence_quote": "Marta: prepare the July sales summary"},
        {"action": "verify the July expense totals", "source_doc": "notes/meeting_notes.md", "evidence_quote": "Sara: verify the July expense totals"},
    ]
    (workspace / "reports/unresolved_actions.json").write_text(json.dumps(entries), encoding="utf-8")
    passed, _ = check_knowledge("knowledge_001", workspace, FIXTURE)
    assert passed is False


def test_autonomy_002_rejects_misaligned_or_duplicate_actions(tmp_path: Path):
    workspace = _workspace(tmp_path)
    entries = [
        {"action": "review software subscriptions", "source_doc": "notes/meeting_notes.md", "evidence_quote": "Francesco: review software subscriptions"},
        {"action": "review software subscriptions", "source_doc": "notes/meeting_notes.md", "evidence_quote": "Francesco: review software subscriptions"},
        {"action": "prepare the July sales summary", "source_doc": "notes/meeting_notes.md", "evidence_quote": "Marta: prepare the July sales summary"},
        {"action": "Launch a rocket to Mars", "source_doc": "notes/meeting_notes.md", "evidence_quote": "Sara: verify the July expense totals"},
    ]
    (workspace / "reports/action_tracker.json").write_text(json.dumps(entries), encoding="utf-8")
    passed, _ = check_data("autonomy_002", workspace, FIXTURE)
    assert passed is False


def test_learning_002_rejects_successful_but_wrong_shifted_schema_result(tmp_path: Path):
    workspace = _workspace(tmp_path)
    (workspace / "skills").mkdir(exist_ok=True)
    (workspace / "skills/reporting_workflow.py").write_text(
        "import argparse\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output');a=p.parse_args();Path(a.output).write_text('Total revenue: 0.00\\n')\n",
        encoding="utf-8",
    )
    (workspace / "reports/learning_transfer.md").write_text("transferred steps: parse\nadapted steps: gross_usd\nadaptation reason: schema shift\n", encoding="utf-8")
    passed, _ = check_data("learning_002", workspace, FIXTURE)
    assert passed is False


def test_long_horizon_003_rejects_requirement_ids_with_fake_evidence(tmp_path: Path):
    workspace = _workspace(tmp_path)
    rows = [{"requirement_id": f"R{i}", "evidence_quote": "totally unrelated evidence"} for i in range(1, 6)]
    (workspace / "reports/audit_matrix.json").write_text(json.dumps(rows), encoding="utf-8")
    (workspace / "reports/final_audit.md").write_text("# Audit\n", encoding="utf-8")
    (workspace / "tools/investigation_helper.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    passed, _ = check_long("long_horizon_003", workspace, FIXTURE)
    assert passed is False
