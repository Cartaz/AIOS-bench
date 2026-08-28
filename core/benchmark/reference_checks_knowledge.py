from __future__ import annotations

import json
import re
from pathlib import Path

from .reference_checks_core import CheckResult, load, ok, read

_STOPWORDS = {
    "a", "an", "and", "as", "at", "be", "by", "for", "from", "in", "is",
    "it", "of", "on", "or", "the", "this", "to", "with",
}


def _text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def _terms(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_.-]+", value.lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _claim_matches_evidence(claim: str, evidence: str) -> bool:
    claim_terms = _terms(claim)
    evidence_terms = _terms(evidence)
    if not claim_terms or not evidence_terms:
        return False
    overlap = claim_terms & evidence_terms
    return len(overlap) >= 2 and len(overlap) / len(claim_terms) >= 0.4


def _valid_procedure_citations(workspace: Path, markdown: str) -> set[str]:
    found: set[str] = set()
    pattern = re.compile(r"\[(?:procedures/)?(previous|current|next_draft)\.md:(\d+)\]", re.I)
    for match in pattern.finditer(markdown):
        name = match.group(1).lower()
        line_number = int(match.group(2))
        path = workspace / "procedures" / f"{name}.md"
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if 1 <= line_number <= len(lines) and lines[line_number - 1].strip():
            found.add(name)
    return found


def _has_all(text: str, *terms: str) -> bool:
    lowered = text.lower()
    return all(term.lower() in lowered for term in terms)


def check(task_id: str, workspace: Path, fixture_root: Path) -> CheckResult:
    del fixture_root
    if task_id == "knowledge_001":
        data = load(workspace, "reports/unresolved_actions.json")
        if not isinstance(data, list) or len(data) != 3:
            return ok(False, "expected three actions")
        good = True
        for entry in data:
            if not isinstance(entry, dict):
                good = False
                break
            source = entry.get("source_doc", "")
            evidence = entry.get("evidence_quote", "")
            action = entry.get("action", "")
            source_path = workspace / str(source)
            if (
                not isinstance(source, str)
                or not source_path.is_file()
                or not isinstance(evidence, str)
                or not evidence
                or evidence not in read(workspace, source)
                or not isinstance(action, str)
                or not _claim_matches_evidence(action, evidence)
            ):
                good = False
                break
        return ok(
            good and not any("Q3 budget" in json.dumps(entry) for entry in data),
            "three grounded unresolved actions with aligned evidence",
        )

    if task_id == "knowledge_002":
        data = load(workspace, "reports/procedure_diff.json")
        markdown = read(workspace, "reports/procedure_diff.md")
        if not isinstance(data, dict):
            return ok(False, "procedure diff JSON must be an object")
        if not all(key in data for key in ("additions", "removals", "changed", "unchanged")):
            return ok(False, "procedure diff JSON missing required categories")

        combined = f"{_text(data)}\n{markdown.lower()}"
        categories = all(
            re.search(rf"\b{name}\b\s*:", markdown, re.I)
            for name in ("additions", "removals", "changed", "unchanged")
        )
        citations = _valid_procedure_citations(workspace, markdown)
        semantic_core = "validation" in combined and "review" in combined
        good = categories and citations == {"previous", "current", "next_draft"} and semantic_core
        return ok(good, "procedure diff has semantic core and three-source provenance")

    if task_id == "knowledge_003":
        data = load(workspace, "reports/claim_evidence.json")
        review = read(workspace, "reports/evidence_review.md")
        if not isinstance(data, list) or len(data) < 3:
            return ok(False, "claim matrix too small")

        grounded = True
        for entry in data:
            if not isinstance(entry, dict):
                grounded = False
                break
            source = entry.get("source_doc", "")
            evidence = entry.get("evidence_quote", "")
            claim = entry.get("claim", "")
            contradictions = entry.get("contradicting_claims")
            source_path = workspace / str(source)
            if (
                not isinstance(source, str)
                or not source_path.is_file()
                or not isinstance(evidence, str)
                or evidence not in read(workspace, source)
                or not isinstance(claim, str)
                or not _claim_matches_evidence(claim, evidence)
                or not isinstance(contradictions, list)
            ):
                grounded = False
                break

        claims_text = _text(data)
        current_workflow_core = all((
            _has_all(claims_text, "export", "monthly", "sales", "csv"),
            _has_all(claims_text, "validate", "header", "numeric"),
            _has_all(claims_text, "revenue", "units"),
        ))
        review_contract = (
            bool(re.search(r"authoritative_source\s*:\s*procedures/current\.md", review, re.I))
            and bool(re.search(r"criteria\s*:\s*\S+", review, re.I))
            and bool(re.search(r"uncertainty\s*:\s*(low|medium|high)", review, re.I))
        )
        return ok(
            grounded and current_workflow_core and review_contract,
            "claim/evidence semantic alignment verified",
        )

    return None
