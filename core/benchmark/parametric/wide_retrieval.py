from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .grading import VariantGrade


SEMANTIC_FIELDS = (
    "record_id",
    "name",
    "category",
    "region",
    "status",
    "score",
    "owner",
)


@dataclass(frozen=True)
class WideRetrievalPressure:
    """Concrete workload coordinates for exhaustive local-corpus retrieval."""

    corpus_size: int = 96
    target_count: int = 12
    duplicate_records: int = 12
    conflict_records: int = 10
    source_depth: int = 3

    def __post_init__(self) -> None:
        if not 24 <= self.corpus_size <= 1000:
            raise ValueError("corpus_size must be between 24 and 1000")
        if not 4 <= self.target_count <= min(96, self.corpus_size // 3):
            raise ValueError(
                "target_count must be between 4 and min(96, corpus_size//3)"
            )
        if not 0 <= self.duplicate_records <= min(256, self.corpus_size):
            raise ValueError(
                "duplicate_records must be between 0 and min(256, corpus_size)"
            )
        if not 1 <= self.conflict_records <= min(256, self.corpus_size):
            raise ValueError(
                "conflict_records must be between 1 and min(256, corpus_size)"
            )
        if not 1 <= self.source_depth <= 6:
            raise ValueError("source_depth must be between 1 and 6")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "WideRetrievalPressure":
        allowed = {
            "corpus_size",
            "target_count",
            "duplicate_records",
            "conflict_records",
            "source_depth",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown wide retrieval pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _record_id(index: int) -> str:
    return f"REC-{index:05d}"


def _target_record(
    rng: random.Random,
    *,
    index: int,
    category: str,
    regions: tuple[str, ...],
    minimum_score: int,
) -> dict[str, Any]:
    return {
        "record_id": _record_id(index),
        "name": f"Generated organization {index:05d}",
        "category": category,
        "region": rng.choice(regions),
        "status": "active",
        "score": rng.randint(minimum_score, 100),
        "owner": f"team-{rng.randint(1, 18):02d}",
    }


def _non_target_record(
    rng: random.Random,
    *,
    index: int,
    category: str,
    regions: tuple[str, ...],
    minimum_score: int,
) -> dict[str, Any]:
    categories = ("analytics", "compute", "network", "storage")
    all_regions = ("apac", "eu", "latam", "us")
    failure = rng.randrange(4)
    row = {
        "record_id": _record_id(index),
        "name": f"Generated organization {index:05d}",
        "category": category,
        "region": rng.choice(regions),
        "status": "active",
        "score": rng.randint(minimum_score, 100),
        "owner": f"team-{rng.randint(1, 18):02d}",
    }
    if failure == 0:
        row["category"] = rng.choice([value for value in categories if value != category])
    elif failure == 1:
        row["region"] = rng.choice([value for value in all_regions if value not in regions])
    elif failure == 2:
        row["status"] = rng.choice(["paused", "retired"])
    else:
        row["score"] = rng.randint(max(1, minimum_score - 25), minimum_score - 1)
    return row


def _authoritative_root(workspace: Path, depth: int) -> Path:
    root = workspace / "corpus" / "current"
    for index in range(1, depth + 1):
        root /= f"level_{index}"
    return root


def _write_shards(
    workspace: Path,
    rows: list[dict[str, Any]],
    *,
    depth: int,
) -> dict[str, dict[str, Any]]:
    root = _authoritative_root(workspace, depth)
    root.mkdir(parents=True, exist_ok=True)
    shard_count = min(12, max(3, math.ceil(len(rows) / 24)))
    shards: list[list[dict[str, Any]]] = [[] for _ in range(shard_count)]
    for index, row in enumerate(sorted(rows, key=lambda item: str(item["record_id"]))):
        shards[index % shard_count].append(row)

    citations: dict[str, dict[str, Any]] = {}
    for shard_index, shard in enumerate(shards, 1):
        path = root / f"shard_{shard_index:02d}.jsonl"
        lines = [json.dumps(row, sort_keys=True, ensure_ascii=False) for row in shard]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        relative = path.relative_to(workspace).as_posix()
        for line_number, row in enumerate(shard, 1):
            citations[str(row["record_id"])] = {
                "path": relative,
                "line": line_number,
            }
    return citations


def _mutate_conflict(
    rng: random.Random,
    row: Mapping[str, Any],
    *,
    category: str,
    regions: tuple[str, ...],
    minimum_score: int,
) -> dict[str, Any]:
    changed = dict(row)
    mutation = rng.randrange(4)
    if mutation == 0:
        changed["status"] = "retired" if row.get("status") == "active" else "active"
    elif mutation == 1:
        changed["score"] = max(1, minimum_score - 1)
    elif mutation == 2:
        changed["category"] = category if row.get("category") != category else "legacy"
    else:
        all_regions = ("apac", "eu", "latam", "us")
        alternate = [value for value in all_regions if value not in regions]
        changed["region"] = rng.choice(alternate)
    changed["owner"] = f"archive-{rng.randint(1, 9):02d}"
    return changed


def generate_wide_retrieval_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: WideRetrievalPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    rng = random.Random(_derived_seed(seed, "wide-retrieval"))

    categories = ("analytics", "compute", "network", "storage")
    regions = ("apac", "eu", "latam", "us")
    category = rng.choice(categories)
    selected_regions = tuple(sorted(rng.sample(regions, 2)))
    minimum_score = rng.choice([72, 76, 80, 84])
    query_id = f"Q-{int(seed):016x}"[-18:]

    rows: list[dict[str, Any]] = []
    target_ids: list[str] = []
    for index in range(1, pressure.target_count + 1):
        row = _target_record(
            rng,
            index=index,
            category=category,
            regions=selected_regions,
            minimum_score=minimum_score,
        )
        rows.append(row)
        target_ids.append(str(row["record_id"]))
    for index in range(pressure.target_count + 1, pressure.corpus_size + 1):
        rows.append(
            _non_target_record(
                rng,
                index=index,
                category=category,
                regions=selected_regions,
                minimum_score=minimum_score,
            )
        )

    citations = _write_shards(workspace, rows, depth=pressure.source_depth)
    authoritative_root = _authoritative_root(workspace, pressure.source_depth)
    authoritative_relative = authoritative_root.relative_to(workspace).as_posix()

    authority_path = workspace / "corpus" / "AUTHORITY.json"
    authority_path.parent.mkdir(parents=True, exist_ok=True)
    authority_path.write_text(
        json.dumps(
            {
                "schema": "aios-bench/wide-retrieval-authority/v1",
                "current_revision": "2026-current",
                "authoritative_root": authoritative_relative,
                "record_format": "jsonl",
                "rule": "Only records under authoritative_root are current authoritative evidence.",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    duplicate_pool = list(rows)
    rng.shuffle(duplicate_pool)
    duplicate_rows = duplicate_pool[: pressure.duplicate_records]
    mirror_path = workspace / "corpus" / "mirrors" / "replica.jsonl"
    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    mirror_path.write_text(
        "\n".join(
            json.dumps(row, sort_keys=True, ensure_ascii=False)
            for row in sorted(duplicate_rows, key=lambda item: str(item["record_id"]))
        )
        + ("\n" if duplicate_rows else ""),
        encoding="utf-8",
    )

    conflict_pool = list(rows)
    target_rows = [row for row in conflict_pool if str(row["record_id"]) in target_ids]
    chosen: list[dict[str, Any]] = []
    # At least one target receives a stale conflicting representation so
    # provenance mistakes are observable in every valid variant.
    chosen.append(rng.choice(target_rows))
    remaining = pressure.conflict_records - 1
    remaining_pool = [row for row in conflict_pool if row is not chosen[0]]
    if remaining:
        chosen.extend(rng.sample(remaining_pool, remaining))
    archive_rows = [
        _mutate_conflict(
            rng,
            row,
            category=category,
            regions=selected_regions,
            minimum_score=minimum_score,
        )
        for row in chosen
    ]
    archive_path = workspace / "corpus" / "archive" / "2025-retired" / "records.jsonl"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(
        "\n".join(
            json.dumps(row, sort_keys=True, ensure_ascii=False)
            for row in sorted(archive_rows, key=lambda item: str(item["record_id"]))
        )
        + "\n",
        encoding="utf-8",
    )

    query_path = workspace / "query" / "current.json"
    query_path.parent.mkdir(parents=True, exist_ok=True)
    query_path.write_text(
        json.dumps(
            {
                "schema": "aios-bench/wide-retrieval-query/v1",
                "query_id": query_id,
                "criteria": {
                    "category": category,
                    "regions": list(selected_regions),
                    "status": "active",
                    "minimum_score": minimum_score,
                },
                "required_fields": list(SEMANTIC_FIELDS),
                "citation": {"path": "authoritative JSONL path", "line": "1-based line number"},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    readme_path = workspace / "README.md"
    readme_path.write_text(
        "# Exhaustive local retrieval\n\n"
        "Read `query/current.json` and `corpus/AUTHORITY.json`. Search the complete authoritative "
        "corpus and return every record satisfying all current query criteria, with no extras. "
        "Archives and mirrors are deliberately plausible but are not authoritative.\n\n"
        "Write exactly `reports/wide_retrieval.json` with this shape:\n\n"
        "```json\n"
        '{"query_id":"...","records":[{"record_id":"...","name":"...","category":"...",'
        '"region":"...","status":"...","score":0,"owner":"...","citation":{"path":"...",'
        '"line":1}}]}\n'
        "```\n\n"
        "Each citation must point to the exact authoritative JSONL file and 1-based line containing "
        "that record. Do not cite mirrors or archives. Do not modify any existing source, query, or "
        "authority file. Record order is irrelevant.\n",
        encoding="utf-8",
    )

    protected_paths = [
        path.relative_to(workspace).as_posix()
        for path in sorted((workspace / "corpus").rglob("*"))
        if path.is_file()
    ]
    protected_paths.extend(["README.md", "query/current.json"])

    by_id = {str(row["record_id"]): dict(row) for row in rows}
    targets = [
        {
            **by_id[record_id],
            "citation": citations[record_id],
        }
        for record_id in sorted(target_ids)
    ]
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "wide_retrieval",
        "scenario": "authoritative_exhaustive_records",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "query_id": query_id,
        "target_rows": targets,
        "authoritative_root": authoritative_relative,
        "archive_prefix": "corpus/archive/",
        "mirror_prefix": "corpus/mirrors/",
        "protected_sha256": {
            relative: _sha256(workspace / relative)
            for relative in sorted(set(protected_paths))
        },
    }
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def _ratio(numerator: int, denominator: int) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0


def _load_report(workspace: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = workspace / "reports" / "wide_retrieval.json"
    if not path.is_file():
        return None, "wide retrieval report missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"wide retrieval report is invalid JSON: {type(exc).__name__}"
    if not isinstance(value, dict) or set(value) != {"query_id", "records"}:
        return None, "wide retrieval report must contain exactly query_id and records"
    if not isinstance(value.get("records"), list):
        return None, "wide retrieval records must be a JSON array"
    return value, None


def grade_wide_retrieval_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> VariantGrade:
    try:
        protected = oracle.get("protected_sha256")
        if not isinstance(protected, Mapping):
            return VariantGrade.binary(False, "wide retrieval protected-source oracle missing")
        for relative, expected in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or _sha256(path) != str(expected):
                return VariantGrade.binary(False, f"protected source modified: {relative}")

        report, error = _load_report(workspace)
        if report is None:
            return VariantGrade.binary(False, error or "wide retrieval report unavailable")
        if report.get("query_id") != oracle.get("query_id"):
            return VariantGrade.binary(False, "wide retrieval query_id mismatch")

        expected_rows = oracle.get("target_rows")
        if not isinstance(expected_rows, list) or not expected_rows:
            return VariantGrade.binary(False, "wide retrieval target oracle missing")
        expected: dict[str, dict[str, Any]] = {}
        for row in expected_rows:
            if not isinstance(row, Mapping) or row.get("record_id") is None:
                return VariantGrade.binary(False, "wide retrieval target oracle malformed")
            expected[str(row["record_id"])] = dict(row)

        raw_predictions = report["records"]
        predictions: list[dict[str, Any]] = [
            dict(row) if isinstance(row, Mapping) else {}
            for row in raw_predictions
        ]
        predicted_ids = [
            str(row.get("record_id"))
            for row in predictions
            if row.get("record_id") is not None
        ]
        unique_predicted = set(predicted_ids)
        expected_ids = set(expected)
        found_ids = unique_predicted & expected_ids
        record_precision = _ratio(len(found_ids), len(predictions))
        record_recall = _ratio(len(found_ids), len(expected_ids))
        record_f1 = _f1(record_precision, record_recall)

        first_by_id: dict[str, dict[str, Any]] = {}
        for row in predictions:
            record_id = row.get("record_id")
            if record_id is not None:
                first_by_id.setdefault(str(record_id), row)

        correct_fields = 0
        total_fields = len(expected_ids) * len(SEMANTIC_FIELDS)
        provenance_correct = 0
        wrong_authority_count = 0
        stale_source_count = 0
        mirror_source_count = 0
        for record_id, expected_row in expected.items():
            predicted = first_by_id.get(record_id)
            if predicted is None:
                continue
            for field in SEMANTIC_FIELDS:
                if predicted.get(field) == expected_row.get(field):
                    correct_fields += 1
            citation = predicted.get("citation")
            expected_citation = expected_row.get("citation")
            if citation == expected_citation:
                provenance_correct += 1
            else:
                path = str(citation.get("path", "")) if isinstance(citation, Mapping) else ""
                if path:
                    wrong_authority_count += 1
                    if path.startswith(str(oracle.get("archive_prefix", "corpus/archive/"))):
                        stale_source_count += 1
                    if path.startswith(str(oracle.get("mirror_prefix", "corpus/mirrors/"))):
                        mirror_source_count += 1

        field_accuracy = _ratio(correct_fields, total_fields)
        provenance_recall = _ratio(provenance_correct, len(expected_ids))
        duplicate_prediction_count = max(0, len(predicted_ids) - len(set(predicted_ids)))
        extra_record_count = len(unique_predicted - expected_ids)
        missing_record_count = len(expected_ids - unique_predicted)
        strict = (
            len(predictions) == len(expected_ids)
            and duplicate_prediction_count == 0
            and extra_record_count == 0
            and missing_record_count == 0
            and record_f1 == 1.0
            and field_accuracy == 1.0
            and provenance_recall == 1.0
        )
        score = (record_f1 + field_accuracy + provenance_recall) / 3.0
        metrics = {
            "strict_complete_pass": strict,
            "record_precision": record_precision,
            "record_recall": record_recall,
            "record_f1": record_f1,
            "field_accuracy": field_accuracy,
            "provenance_recall": provenance_recall,
            "expected_records": len(expected_ids),
            "predicted_rows": len(predictions),
            "missing_record_count": missing_record_count,
            "extra_record_count": extra_record_count,
            "duplicate_prediction_count": duplicate_prediction_count,
            "wrong_authority_count": wrong_authority_count,
            "stale_source_count": stale_source_count,
            "mirror_source_count": mirror_source_count,
        }
        if record_recall < 1.0:
            failure_kind = "INCOMPLETE_RETRIEVAL"
        elif provenance_recall < 1.0:
            failure_kind = "WRONG_AUTHORITY"
        else:
            failure_kind = None
        detail = (
            f"strict={strict}; record_f1={record_f1:.4f}; "
            f"field_accuracy={field_accuracy:.4f}; provenance_recall={provenance_recall:.4f}"
        )
        return VariantGrade(
            passed=strict,
            detail=detail,
            score=score,
            metrics=metrics,
            failure_kind=failure_kind,
        )
    except (OSError, TypeError, ValueError, KeyError) as exc:
        return VariantGrade.binary(
            False,
            f"wide retrieval oracle error: {type(exc).__name__}: {exc}",
        )


def check_wide_retrieval_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> tuple[bool, str]:
    grade = grade_wide_retrieval_variant(workspace, oracle)
    return grade.passed, grade.detail


__all__ = [
    "SEMANTIC_FIELDS",
    "WideRetrievalPressure",
    "check_wide_retrieval_variant",
    "generate_wide_retrieval_variant",
    "grade_wide_retrieval_variant",
]
