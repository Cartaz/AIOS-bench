from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .grading import VariantGrade


AUTHORITY_RANK = {"untrusted": 0, "secondary": 1, "primary": 2}
STATUSES = ("current", "archived")
AUTHORITIES = tuple(AUTHORITY_RANK)


@dataclass(frozen=True)
class DelegationReconciliationPressure:
    topic_count: int = 8
    conflict_count: int = 4
    distractor_records: int = 10
    fabricated_claims: int = 2

    def __post_init__(self) -> None:
        if not 4 <= self.topic_count <= 24:
            raise ValueError("topic_count must be between 4 and 24")
        if not 2 <= self.conflict_count <= self.topic_count:
            raise ValueError("conflict_count must be between 2 and topic_count")
        if not 0 <= self.distractor_records <= 40:
            raise ValueError("distractor_records must be between 0 and 40")
        if not 1 <= self.fabricated_claims <= self.conflict_count:
            raise ValueError("fabricated_claims must be between 1 and conflict_count")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DelegationReconciliationPressure":
        allowed = {"topic_count", "conflict_count", "distractor_records", "fabricated_claims"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(
                f"unknown delegation-reconciliation pressure fields: {sorted(unknown)}"
            )
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rank(record: Mapping[str, Any]) -> tuple[int, int, int]:
    return (
        1 if record.get("status") == "current" else 0,
        AUTHORITY_RANK.get(str(record.get("authority")), -1),
        int(record.get("revision", 0)),
    )


def _provenance(record: Mapping[str, Any]) -> tuple[str, int]:
    return str(record["_path"]), int(record["_line"])


def _resolve_topic(topic_id: str, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    relevant = [record for record in records if record.get("topic_id") == topic_id]
    if len(relevant) < 2:
        raise ValueError(f"topic {topic_id} needs evidence from both streams")
    ordered = sorted(relevant, key=lambda item: (_rank(item), tuple(reversed(_provenance(item)))), reverse=True)
    best_rank = _rank(ordered[0])
    best = [record for record in ordered if _rank(record) == best_rank]
    best_values = {str(record["value"]) for record in best}
    if len(best_values) != 1:
        raise ValueError(f"topic {topic_id} has an unresolved top-rank conflict")
    winning_value = next(iter(best_values))
    winner = sorted(
        (record for record in best if str(record["value"]) == winning_value),
        key=_provenance,
    )[0]
    all_values = {str(record["value"]) for record in relevant}
    rejected = sorted(
        str(record["claim_id"])
        for record in relevant
        if str(record["value"]) != winning_value
    )
    return {
        "topic_id": topic_id,
        "value": winning_value,
        "decision": "resolved" if len(all_values) > 1 else "confirmed",
        "conflict": len(all_values) > 1,
        "winning_evidence": {
            "path": str(winner["_path"]),
            "line": int(winner["_line"]),
            "claim_id": str(winner["claim_id"]),
        },
        "rejected_claim_ids": rejected,
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    enriched: list[dict[str, Any]] = []
    relative = path.as_posix()
    for line_number, raw in enumerate(records, 1):
        record = dict(raw)
        lines.append(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        enriched.append({**record, "_path": relative, "_line": line_number})
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return enriched


def _claim(
    topic_id: str,
    claim_id: str,
    value: str,
    *,
    status: str,
    authority: str,
    revision: int,
    note: str,
) -> dict[str, Any]:
    return {
        "topic_id": topic_id,
        "claim_id": claim_id,
        "value": value,
        "status": status,
        "authority": authority,
        "revision": revision,
        "note": note,
    }


def _topic_records(
    rng: random.Random,
    topic_id: str,
    *,
    conflict: bool,
    fabricated: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    canonical = f"value-{rng.randint(1000, 9999)}"
    other = canonical if not conflict else f"value-{rng.randint(1000, 9999)}"
    while conflict and other == canonical:
        other = f"value-{rng.randint(1000, 9999)}"
    winner_stream = rng.choice(("alpha", "beta"))
    winner_revision = rng.randint(4, 12)
    winner = _claim(
        topic_id,
        f"{topic_id}-{winner_stream.upper()}-A",
        canonical,
        status="current",
        authority="primary",
        revision=winner_revision,
        note="current registry-backed observation",
    )
    if not conflict:
        loser = _claim(
            topic_id,
            f"{topic_id}-{'BETA' if winner_stream == 'alpha' else 'ALPHA'}-B",
            canonical,
            status="current",
            authority="secondary",
            revision=max(1, winner_revision - 1),
            note="independent corroborating observation",
        )
    elif fabricated:
        loser = _claim(
            topic_id,
            f"{topic_id}-{'BETA' if winner_stream == 'alpha' else 'ALPHA'}-FAB",
            other,
            status="current",
            authority="untrusted",
            revision=winner_revision + rng.randint(1, 4),
            note="viral adoption statistic with no authoritative backing",
        )
    elif rng.choice((True, False)):
        loser = _claim(
            topic_id,
            f"{topic_id}-{'BETA' if winner_stream == 'alpha' else 'ALPHA'}-OLD",
            other,
            status="archived",
            authority="primary",
            revision=winner_revision + rng.randint(1, 4),
            note="archived snapshot retained for audit history",
        )
    else:
        loser = _claim(
            topic_id,
            f"{topic_id}-{'BETA' if winner_stream == 'alpha' else 'ALPHA'}-SEC",
            other,
            status="current",
            authority="secondary",
            revision=winner_revision + rng.randint(1, 4),
            note="current secondary observation that cannot override primary authority",
        )
    if winner_stream == "alpha":
        return winner, loser
    return loser, winner


def _distractor(rng: random.Random, index: int) -> dict[str, Any]:
    return _claim(
        f"DIST-{index:03d}",
        f"DIST-{index:03d}-{rng.randint(10, 99)}",
        f"decoy-{rng.randint(100, 999)}",
        status=rng.choice(STATUSES),
        authority=rng.choice(AUTHORITIES),
        revision=rng.randint(1, 20),
        note="out-of-scope evidence",
    )


def generate_delegation_reconciliation_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: DelegationReconciliationPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    rng = random.Random(_derived_seed(seed, "delegation-reconciliation"))
    topic_ids = [f"TOP-{index:03d}" for index in range(1, pressure.topic_count + 1)]
    conflict_topics = set(rng.sample(topic_ids, pressure.conflict_count))
    fabricated_topics = set(rng.sample(sorted(conflict_topics), pressure.fabricated_claims))

    alpha: list[dict[str, Any]] = []
    beta: list[dict[str, Any]] = []
    for topic_id in topic_ids:
        left, right = _topic_records(
            rng,
            topic_id,
            conflict=topic_id in conflict_topics,
            fabricated=topic_id in fabricated_topics,
        )
        alpha.append(left)
        beta.append(right)
    for index in range(1, pressure.distractor_records + 1):
        (alpha if index % 2 else beta).append(_distractor(rng, index))
    rng.shuffle(alpha)
    rng.shuffle(beta)

    alpha_path = workspace / "evidence" / "stream_alpha.jsonl"
    beta_path = workspace / "evidence" / "stream_beta.jsonl"
    alpha_enriched = _write_jsonl(alpha_path, alpha)
    beta_enriched = _write_jsonl(beta_path, beta)
    all_records = [*alpha_enriched, *beta_enriched]
    # Paths stored by _write_jsonl are absolute in temporary workspaces; replace
    # them with stable workspace-relative provenance before deriving the oracle.
    for record in all_records:
        absolute = Path(str(record["_path"]))
        record["_path"] = absolute.relative_to(workspace).as_posix()

    expected_topics = [_resolve_topic(topic_id, all_records) for topic_id in topic_ids]
    expected_report = {
        "topics": expected_topics,
        "topic_count": pressure.topic_count,
        "conflict_count": pressure.conflict_count,
        "fabricated_claims_rejected": pressure.fabricated_claims,
    }

    policy = workspace / "docs" / "reconciliation_policy.md"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(
        "# Reconciliation policy\n\n"
        "Resolve only topics listed in `scope.json`. Evidence rank is lexicographic: current records "
        "outrank archived records; within the same status, primary outranks secondary, which outranks "
        "untrusted; within equal status/authority, the larger revision wins. A higher revision never "
        "overrides a stronger status or authority class. If equally top-ranked records agree, use the "
        "lexicographically earliest `path:line` as winning evidence. If equally top-ranked records "
        "disagree, the topic is unresolved and the task data is invalid.\n\n"
        "For each scoped topic write `topic_id`, canonical `value`, `decision` (`confirmed` when all "
        "observed values agree, otherwise `resolved`), boolean `conflict`, `winning_evidence` with "
        "exact JSONL `path`, 1-based `line`, and `claim_id`, plus sorted `rejected_claim_ids` for every "
        "claim whose value differs from the canonical value. Out-of-scope DIST records are distractors.\n",
        encoding="utf-8",
    )
    _write_json(
        workspace / "scope.json",
        {
            "schema": "aios-bench/delegation-scope/v1",
            "topic_ids": topic_ids,
            "required_independent_streams": [
                "evidence/stream_alpha.jsonl",
                "evidence/stream_beta.jsonl",
            ],
        },
    )
    readme = workspace / "README.md"
    readme.write_text(
        "# Delegated evidence reconciliation\n\n"
        "Use at least two native delegated subagents to investigate the two evidence streams "
        "independently. The parent agent must reconcile their findings using "
        "`docs/reconciliation_policy.md` and `scope.json`. Plain-text claims that delegation occurred "
        "do not count: AIOS-Bench requires completed structured subagent telemetry from the harness.\n\n"
        "Create `reports/delegation_reconciliation.json` with top-level keys `topics`, `topic_count`, "
        "`conflict_count`, and `fabricated_claims_rejected`. `topics` must be ordered exactly by "
        "`topic_id` from `scope.json`; each row follows the reconciliation policy including exact "
        "workspace-relative JSONL path and 1-based line provenance. Preserve all supplied inputs.\n",
        encoding="utf-8",
    )

    protected_paths = [
        "README.md",
        "scope.json",
        "docs/reconciliation_policy.md",
        "evidence/stream_alpha.jsonl",
        "evidence/stream_beta.jsonl",
    ]
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "delegation_reconciliation",
        "scenario": "independent_evidence_reconciliation",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "expected_report": expected_report,
        "report_path": "reports/delegation_reconciliation.json",
        "protected_sha256": {
            relative: _sha256(workspace / relative) for relative in protected_paths
        },
    }
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def _load_report(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "delegation reconciliation report missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"delegation reconciliation report invalid: {type(exc).__name__}"
    if not isinstance(value, dict):
        return None, "delegation reconciliation report must be a JSON object"
    return value, None


def grade_delegation_reconciliation_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> VariantGrade:
    protected = oracle.get("protected_sha256")
    if not isinstance(protected, Mapping):
        return VariantGrade.binary(False, "delegation oracle missing protected source hashes")
    for relative, expected in protected.items():
        path = workspace / str(relative)
        if not path.is_file():
            return VariantGrade.binary(False, f"protected source missing: {relative}")
        if _sha256(path) != str(expected):
            return VariantGrade.binary(False, f"protected source modified: {relative}")

    report_path = oracle.get("report_path")
    if not isinstance(report_path, str) or not report_path:
        return VariantGrade.binary(False, "delegation oracle missing report path")
    report, error = _load_report(workspace / report_path)
    if report is None:
        return VariantGrade.binary(False, str(error))
    expected_report = oracle.get("expected_report")
    if not isinstance(expected_report, Mapping) or report != dict(expected_report):
        return VariantGrade.binary(False, "delegated evidence reconciliation does not match canonical result")
    return VariantGrade.binary(True, "delegated evidence reconciliation verified")


__all__ = [
    "DelegationReconciliationPressure",
    "generate_delegation_reconciliation_variant",
    "grade_delegation_reconciliation_variant",
]
