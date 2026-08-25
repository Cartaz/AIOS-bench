from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ATTEMPT_SCHEMA = "aios-bench/task-attempt/v1"
SOURCE_INDEX_SCHEMA = "aios-bench/raw-source-index/v1"

_METADATA_FIELDS = (
    "harness",
    "model",
    "run_id",
    "suite",
    "suite_revision",
    "git_commit",
    "git_dirty",
    "execution_fingerprint",
    "started_at",
    "finished_at",
    "task_count",
    "dry_run",
    "run_type",
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_bytes(payload.encode("utf-8"))


def _manifest_for_results(path: Path) -> dict[str, Any]:
    metadata_path = path.parent / "run.json"
    try:
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def enrich_attempt(row: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    """Attach authoritative run metadata to one raw task observation."""
    enriched = dict(row)
    for field in _METADATA_FIELDS:
        if field in metadata:
            enriched[field] = metadata[field]
    if "status" in metadata:
        enriched["run_status"] = metadata["status"]
    enriched.setdefault("harness", enriched.get("agent", "unknown"))
    enriched.setdefault("model", "unknown")
    enriched.setdefault("run_id", "legacy")
    enriched.setdefault("suite", "legacy")
    enriched.setdefault("suite_revision", "legacy")
    return enriched


def _attempt_id(row: dict[str, Any], attempt_index: int) -> str:
    identity = {
        "harness": str(row.get("harness", row.get("agent", "unknown"))),
        "model": str(row.get("model", "unknown")),
        "suite": str(row.get("suite", "legacy")),
        "suite_revision": str(row.get("suite_revision", "legacy")),
        "run_id": str(row.get("run_id", "legacy")),
        "task_id": str(row.get("task_id", "unknown")),
        "attempt_index": int(attempt_index),
    }
    return _canonical_sha256(identity)[:32]


def _unique_result_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for path in sorted(root.rglob("results.jsonl")):
        if not path.is_file():
            continue
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path.absolute()
        if resolved in seen:
            continue
        seen.add(resolved)
        paths.append(path)
    return paths


def load_attempts(root: Path) -> list[dict[str, Any]]:
    """Load every valid raw task observation without deduplicating attempts.

    Attempt identity is derived from the authoritative journal order, so legacy
    rows and rows containing stale/spoofed identity fields are handled the same
    way. The physical JSONL remains the raw source; these fields make each
    observation addressable in derived analysis.
    """
    attempts: list[dict[str, Any]] = []
    for path in _unique_result_files(root):
        metadata = _manifest_for_results(path)
        counters: dict[str, int] = defaultdict(int)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict):
                continue
            row = enrich_attempt(value, metadata)
            task_id = str(row.get("task_id", "unknown"))
            counters[task_id] += 1
            index = counters[task_id]
            row["attempt_schema"] = ATTEMPT_SCHEMA
            row["attempt_index"] = index
            row["attempt_id"] = _attempt_id(row, index)
            try:
                source_path = path.relative_to(root).as_posix()
            except ValueError:
                source_path = path.as_posix()
            row["source_path"] = source_path
            row["source_line"] = line_number
            attempts.append(row)
    return attempts


def latest_attempts(attempts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive the latest observation per run/task from an attempt stream."""
    latest: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    for row in attempts:
        key = (
            str(row.get("harness", row.get("agent", "unknown"))),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
            str(row.get("run_id", "legacy")),
            str(row.get("task_id", "unknown")),
        )
        latest[key] = row
    return list(latest.values())


def source_index(root: Path) -> dict[str, Any]:
    """Hash the local raw files that are sufficient to regenerate analysis."""
    entries: list[dict[str, Any]] = []
    seen: set[Path] = set()
    candidates = sorted([*root.rglob("run.json"), *root.rglob("results.jsonl")])
    for path in candidates:
        if not path.is_file():
            continue
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path.absolute()
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            content = path.read_bytes()
        except OSError:
            continue
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = path.as_posix()
        entries.append({
            "path": relative,
            "sha256": _sha256_bytes(content),
            "bytes": len(content),
        })
    entries.sort(key=lambda item: item["path"])
    return {
        "schema": SOURCE_INDEX_SCHEMA,
        "file_count": len(entries),
        "files": entries,
        "digest": _canonical_sha256(entries),
    }
