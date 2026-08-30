from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .ablations import skill_ablation_pairs
from .cross_artifact_analysis import cross_artifact_metrics
from .landscapes import pressure_landscapes, pressure_paired_comparisons
from .raw import latest_attempts, load_attempts, source_index
from .retrieval_analysis import wide_retrieval_metrics


ANALYSIS_SCHEMA = "aios-bench/derived-analysis/v1"
_IDENTITY_FIELDS = ("harness", "model", "run_id", "suite", "suite_revision")
_METADATA_FIELDS = (
    *_IDENTITY_FIELDS,
    "git_commit",
    "git_dirty",
    "execution_fingerprint",
    "started_at",
    "finished_at",
    "task_count",
    "dry_run",
    "run_type",
)


def _text(value: Any, default: str) -> str:
    return str(value) if value not in (None, "") else default


def _intervention_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    manifest = metadata.get("manifest")
    if not isinstance(manifest, dict):
        return {}
    intervention = manifest.get("intervention")
    if not isinstance(intervention, dict):
        return {}
    return {
        key: intervention[key]
        for key in ("schema", "skill_mode", "skill_catalog_digest")
        if key in intervention
    }


def _enrich(row: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    """Attach authoritative run metadata without exposing an internal wrapper."""
    enriched = dict(row)
    for field in _METADATA_FIELDS:
        if field in metadata:
            enriched[field] = metadata[field]
    intervention = _intervention_metadata(metadata)
    if intervention:
        enriched["intervention_schema"] = intervention.get("schema")
        enriched["skill_mode"] = intervention.get("skill_mode")
        enriched["skill_catalog_digest"] = intervention.get("skill_catalog_digest")
    if "status" in metadata:
        enriched["run_status"] = metadata["status"]
    enriched.setdefault("harness", enriched.get("agent", "unknown"))
    enriched.setdefault("model", "unknown")
    enriched.setdefault("run_id", "legacy")
    enriched.setdefault("suite", "legacy")
    enriched.setdefault("suite_revision", "legacy")
    return enriched


def load_results(root: Path) -> list[dict[str, Any]]:
    """Derived compatibility view: keep only the latest attempt per run/task."""
    return latest_attempts(load_attempts(root))


def canonical_capability_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return baseline rows suitable for capability/reliability leaderboards.

    `no_skill` is the Frontier v4 baseline condition. Curated guidance is an
    experimental intervention and is analyzed only through the dedicated
    matched-ablation path so it cannot inflate canonical capability metrics.
    Legacy rows without intervention metadata remain baseline-compatible.
    """
    return [
        row
        for row in rows
        if row.get("skill_mode") in {None, "", "no_skill"}
    ]


def _run_key(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        _text(item.get("harness", item.get("agent")), "unknown"),
        _text(item.get("model"), "unknown"),
        _text(item.get("suite"), "legacy"),
        _text(item.get("suite_revision"), "legacy"),
        _text(item.get("run_id"), "legacy"),
    )


def _manifests(root: Path) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    manifests: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    seen_paths: set[Path] = set()
    for path in sorted(root.rglob("run.json")):
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path.absolute()
        if resolved in seen_paths or not path.is_file():
            continue
        seen_paths.add(resolved)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict):
            continue
        normalized = _enrich({}, value)
        manifests[_run_key(normalized)] = normalized
    return manifests


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _is_comparable(row: dict[str, Any]) -> bool:
    return row.get("status") != "unsupported" and row.get("comparable") is not False


def _is_dry_run(metadata: dict[str, Any]) -> bool:
    if metadata.get("dry_run") is True:
        return True
    if _text(metadata.get("run_type"), "").lower() in {"dry-run", "dry_run", "dryrun"}:
        return True
    for field in ("run_id", "model"):
        compact = _text(metadata.get(field), "").lower().replace("_", "").replace("-", "")
        if "dryrun" in compact:
            return True
    return False


def _summarize_run(metadata: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [item for item in items if _is_comparable(item)]
    scores = [score for item in comparable if (score := _number(item.get("score"))) is not None]
    categories: dict[str, list[float]] = defaultdict(list)
    tiers: dict[str, list[float]] = defaultdict(list)
    for item in comparable:
        score = _number(item.get("score"))
        if score is None:
            continue
        categories[_text(item.get("category"), "unknown")].append(score)
        tiers[_text(item.get("tier"), "unknown")].append(score)

    expected_raw = metadata.get("task_count")
    try:
        expected = int(expected_raw) if expected_raw is not None else None
    except (TypeError, ValueError):
        expected = None
    declared_status = _text(metadata.get("run_status", metadata.get("status")), "unknown").lower()
    exact_task_count = expected is not None and expected >= 0 and len(items) == expected
    complete = exact_task_count and declared_status == "completed"

    suite = _text(metadata.get("suite"), "legacy")
    suite_revision = _text(metadata.get("suite_revision"), "legacy")
    legacy = suite.lower() == "legacy" or suite_revision.lower() == "legacy"
    dry_run = _is_dry_run(metadata)
    skill_mode_raw = metadata.get("skill_mode")
    if skill_mode_raw in (None, "") and items:
        skill_mode_raw = items[0].get("skill_mode")
    skill_mode = str(skill_mode_raw) if skill_mode_raw not in (None, "") else None
    experimental_intervention = skill_mode not in {None, "no_skill"}
    eligible = complete and not legacy and not dry_run and not experimental_intervention
    if legacy:
        eligibility_reason = "legacy"
    elif dry_run:
        eligibility_reason = "dry_run"
    elif experimental_intervention:
        eligibility_reason = "experimental_intervention"
    elif not complete:
        eligibility_reason = "incomplete"
    else:
        eligibility_reason = "eligible"

    durations = [
        value for item in comparable
        if (value := _number(item.get("duration_seconds"))) is not None
    ]
    passed = sum(bool(item.get("success")) for item in comparable)
    return {
        "run_id": _text(metadata.get("run_id"), "legacy"),
        "harness": _text(metadata.get("harness", metadata.get("agent")), "unknown"),
        "model": _text(metadata.get("model"), "unknown"),
        "suite": suite,
        "suite_revision": suite_revision,
        "git_commit": _text(metadata.get("git_commit"), "unknown"),
        "git_dirty": metadata.get("git_dirty"),
        "execution_fingerprint": metadata.get("execution_fingerprint"),
        "skill_mode": skill_mode,
        "skill_catalog_digest": metadata.get("skill_catalog_digest"),
        "started_at": metadata.get("started_at"),
        "finished_at": metadata.get("finished_at"),
        "status": declared_status,
        "complete": complete,
        "eligible": eligible,
        "eligibility_reason": eligibility_reason,
        "tasks": len(items),
        "expected_tasks": expected,
        "comparable_tasks": len(comparable),
        "unsupported": sum(item.get("status") == "unsupported" for item in items),
        "blocked": sum(item.get("status") == "blocked" for item in items),
        "noncomparable": len(items) - len(comparable),
        "passed": passed,
        "success_rate": passed / len(comparable) * 100 if comparable else 0.0,
        "mean_score": sum(scores) / len(scores) if scores else None,
        "scored_tasks": len(scores),
        "runtime_seconds": sum(durations),
        "telemetry_rate": (
            sum(bool(item.get("telemetry_available")) for item in comparable) / len(comparable) * 100
            if comparable else 0.0
        ),
        "categories": {key: sum(values) / len(values) for key, values in sorted(categories.items())},
        "tiers": {key: sum(values) / len(values) for key, values in sorted(tiers.items())},
    }


def summarize_rows(
    rows: Iterable[dict[str, Any]],
    manifests: dict[tuple[str, str, str, str, str], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    metadata_by_key = dict(manifests or {})
    for row in rows:
        key = _run_key(row)
        groups[key].append(row)
        metadata_by_key.setdefault(key, row)
    for key in metadata_by_key:
        groups.setdefault(key, [])
    return [_summarize_run(metadata_by_key[key], groups[key]) for key in sorted(groups)]


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def selected_suite_revision(runs: Iterable[dict[str, Any]]) -> tuple[str, str] | None:
    """Choose the newest observed real suite identity from lifecycle metadata."""
    candidates = [
        run for run in runs
        if run.get("eligibility_reason") not in {"legacy", "dry_run"}
    ]
    if not candidates:
        return None
    selected = max(
        candidates,
        key=lambda run: (
            _timestamp(run.get("started_at")),
            _timestamp(run.get("finished_at")),
            _text(run.get("suite"), "legacy"),
            _text(run.get("suite_revision"), "legacy"),
        ),
    )
    return (
        _text(selected.get("suite"), "legacy"),
        _text(selected.get("suite_revision"), "legacy"),
    )


def latest_eligible(runs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select latest complete harness/model runs on the current suite revision."""
    items = list(runs)
    selected = selected_suite_revision(items)
    if selected is None:
        return []
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for run in items:
        if not run.get("eligible"):
            continue
        identity = (
            _text(run.get("suite"), "legacy"),
            _text(run.get("suite_revision"), "legacy"),
        )
        if identity != selected:
            continue
        key = (_text(run.get("harness"), "unknown"), _text(run.get("model"), "unknown"))
        candidate_order = (
            _timestamp(run.get("finished_at")),
            _timestamp(run.get("started_at")),
            _text(run.get("run_id"), "legacy"),
        )
        current = latest.get(key)
        if current is None:
            latest[key] = run
            continue
        current_order = (
            _timestamp(current.get("finished_at")),
            _timestamp(current.get("started_at")),
            _text(current.get("run_id"), "legacy"),
        )
        if candidate_order > current_order:
            latest[key] = run
    return [latest[key] for key in sorted(latest)]


def build_summary(root: Path) -> dict[str, Any]:
    attempts = load_attempts(root)
    rows = latest_attempts(attempts)
    canonical_rows = canonical_capability_rows(rows)
    runs = summarize_rows(rows, _manifests(root))
    selected = selected_suite_revision(runs)
    sources = source_index(root)
    filters = {
        "suite": selected[0] if selected else None,
        "suite_revision": selected[1] if selected else None,
    }
    return {
        "analysis_schema": ANALYSIS_SCHEMA,
        "runs": runs,
        "leaderboard": latest_eligible(runs),
        "selected_suite": selected[0] if selected else None,
        "selected_suite_revision": selected[1] if selected else None,
        "raw_attempt_count": len(attempts),
        "result_count": len(rows),
        "canonical_result_count": len(canonical_rows),
        "raw_source_digest": sources["digest"],
        "raw_source_file_count": sources["file_count"],
        "pressure_landscapes": pressure_landscapes(canonical_rows, **filters),
        "pressure_paired_comparisons": pressure_paired_comparisons(canonical_rows, **filters),
        "wide_retrieval_metrics": wide_retrieval_metrics(canonical_rows, **filters),
        "cross_artifact_metrics": cross_artifact_metrics(canonical_rows, **filters),
        "skill_ablations": skill_ablation_pairs(rows, **filters),
    }


def write_summary(root: Path, output_dir: Path | None = None) -> Path:
    destination = output_dir or root
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "summary.json"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(build_summary(root), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path
