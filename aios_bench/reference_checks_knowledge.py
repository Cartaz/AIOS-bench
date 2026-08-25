from __future__ import annotations

import json
import re

from .reference_checks_core import load, ok, read


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


def _valid_procedure_citations(workspace, markdown: str) -> set[str]:
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


def check(t, w, fx):
    if t == "knowledge_001":
        data = load(w, "reports/unresolved_actions.json")
        if not isinstance(data, list) or len(data) != 3:
            return ok(False, "expected three actions")
        good = all(
            (w / entry.get("source_doc", "")).is_file()
            and entry.get("evidence_quote", "") in read(w, entry["source_doc"])
            for entry in data
        )
        return ok(
            good and not any("Q3 budget" in json.dumps(entry) for entry in data),
            "three grounded unresolved actions",
        )

    if t == "knowledge_002":
        data = load(w, "reports/procedure_diff.json")
        markdown = read(w, "reports/procedure_diff.md")
        if not isinstance(data, dict):
            return ok(False, "procedure diff JSON must be an object")
        if not all(key in data for key in ("additions", "removals", "changed", "unchanged")):
            return ok(False, "procedure diff JSON missing required categories")

        combined = f"{_text(data)}\n{markdown.lower()}"
        categories = all(
            re.search(rf"\b{name}\b\s*:", markdown, re.I)
            for name in ("additions", "removals", "changed", "unchanged")
        )
        citations = _valid_procedure_citations(w, markdown)

        semantic_facts = (
            _has_all(combined, "export", "monthly", "sales", "csv"),
            _has_all(combined, "validate", "header", "numeric"),
            _has_all(combined, "revenue", "units"),
            "monthly-sales.txt" in combined and "monthly-sales.md" in combined,
            _has_all(combined, "review", "sharing"),
            ("project pr workflow" in combined or "pull request" in combined),
            ("operator impact" in combined or "operator_impact" in combined),
        )
        good = categories and citations == {"previous", "current", "next_draft"} and all(semantic_facts)
        return ok(good, "semantic procedure diff with valid provenance")

    if t == "knowledge_003":
        data = load(w, "reports/claim_evidence.json")
        review = read(w, "reports/evidence_review.md")
        if not isinstance(data, list) or len(data) < 4:
            return ok(False, "claim matrix too small")

        grounded = True
        contradiction_count = 0
        for entry in data:
            source = entry.get("source_doc", "")
            evidence = entry.get("evidence_quote", "")
            claim = entry.get("claim", "")
            contradictions = entry.get("contradicting_claims")
            source_path = w / source
            if (
                not isinstance(source, str)
                or not source_path.is_file()
                or not isinstance(evidence, str)
                or evidence not in read(w, source)
                or not isinstance(claim, str)
                or not _claim_matches_evidence(claim, evidence)
                or not isinstance(contradictions, list)
            ):
                grounded = False
                break
            contradiction_count += len(contradictions)

        claims_text = _text(data)
        current_workflow = all((
            _has_all(claims_text, "export", "monthly", "sales", "csv"),
            _has_all(claims_text, "validate", "header", "numeric"),
            _has_all(claims_text, "revenue", "units"),
            "monthly-sales.md" in claims_text,
            _has_all(claims_text, "review", "sharing"),
        ))
        review_contract = (
            bool(re.search(r"authoritative_source\s*:\s*procedures/current\.md", review, re.I))
            and bool(re.search(r"criteria\s*:\s*\S+", review, re.I))
            and bool(re.search(r"uncertainty\s*:\s*(low|medium|high)", review, re.I))
        )
        good = grounded and contradiction_count >= 1 and current_workflow and review_contract
        return ok(good, "claim/evidence semantics and contradictions verified")

    return None
