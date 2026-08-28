from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_documents_ui_language_logging_and_catalog_boundary() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "desktop UI is currently Italian" in readme
    assert "XDG_STATE_HOME" in readme
    assert "benchmarks/tasks/frontier_v3/" in readme
    assert "historical assets" in readme
    assert "AIOS_BENCH_AGENTZERO_API_KEY" in readme
    assert "AIOS_BENCH_CLAUDE_API_KEY" in readme
    assert "ANTHROPIC_API_KEY" in readme
    assert "subprocess credential scrubbing" in readme


def test_results_readme_distinguishes_verified_and_historical_snapshots() -> None:
    readme = (ROOT / "results" / "README.md").read_text(encoding="utf-8")
    assert "historical snapshots only" in readme
    assert "publication.json" in readme


def test_strategic_review_records_post_audit_milestone() -> None:
    review = (ROOT / "docs" / "STRATEGIC_REVIEW.md").read_text(encoding="utf-8")
    assert "Post-audit corrective milestone" in review
    assert "Doctor inspection" in review
    assert "PreparedRun" in review


def test_audit_remediation_matrix_tracks_all_findings_and_pending_validation() -> None:
    remediation = (ROOT / "docs" / "AUDIT_2026-08-28_REMEDIATION.md").read_text(encoding="utf-8")
    for number in range(1, 14):
        assert f"F{number} —" in remediation
    assert "not merge-validated yet" in remediation
    assert ".venv/bin/python -m pytest" in remediation
    assert ".venv/bin/ruff check" in remediation
