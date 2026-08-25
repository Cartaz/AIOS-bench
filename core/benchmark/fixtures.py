"""Deterministic materializers for benchmark inputs that would be bulky in git."""

from __future__ import annotations

from pathlib import Path


LONG_HORIZON_PACKET_COUNT = 80
LONG_HORIZON_MIN_BYTES = 50_000


def materialize_long_horizon_corpus(workspace: Path) -> Path:
    """Create a >50 KiB, grounded corpus inside one isolated task workspace.

    The generated documents deliberately contain near-duplicate operational
    updates.  One late, signed release gate supersedes the earlier drafts;
    agents must locate and cite it instead of relying on a filename or a
    generic summary.  Generation keeps the repository compact while preserving
    an identical corpus for every harness and every run.
    """
    corpus = workspace / "research" / "long_horizon_corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    index: list[str] = ["# Long-horizon operational corpus", "", "Read packet contents; filenames are not authority signals.", ""]
    for number in range(1, LONG_HORIZON_PACKET_COUNT + 1):
        packet_id = f"LH-{number:03d}"
        status = "draft" if number < 47 else "reviewed"
        text = f"""# Operational packet {packet_id}

Status: {status}
This packet records a regional reporting rehearsal. Earlier packets often
contain superseded assumptions, incomplete ownership assignments, or rollback
suggestions. Treat a statement as binding only when it identifies a signed
release gate and reconcile it with later evidence rather than averaging values.

Evidence stream: batch {number:03d} processed a synthetic ledger of 12,480
records. The observed latency was {180 + (number % 23)} ms and the provisional
rollback contact was rotation-{number % 9}. These figures are historical
context only; they are intentionally plausible distractors for the final
decision. Validation notes require a checkpoint before every irreversible
operation and a recovery note after any validator failure.

Operator note: document the source packet, distinguish verified facts from
tentative recommendations, and preserve the dependency between validation,
recovery, and release approval. Do not treat this packet title as proof of
authority.
"""
        if number == 47:
            text += """
## Signed release gate

Gate ID: LH-047
Authority: release council record, signed after reconciliation
Decision: proceed only when the p95 latency budget is at most 240 ms.
Rollback owner: Priya N.
This signed gate supersedes every provisional latency or rotation-contact value
in the surrounding packets. Cite this packet when reporting the final gate.
"""
        path = corpus / f"packet_{number:03d}.md"
        path.write_text(text, encoding="utf-8")
        index.append(f"- {path.name}: packet {packet_id}")
    (corpus / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    total_bytes = sum(path.stat().st_size for path in corpus.rglob("*") if path.is_file())
    if total_bytes < LONG_HORIZON_MIN_BYTES:  # defensive invariant for template edits
        raise RuntimeError(f"long-horizon corpus is too small: {total_bytes} bytes")
    return corpus
