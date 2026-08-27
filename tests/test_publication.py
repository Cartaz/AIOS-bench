from __future__ import annotations

import json
from pathlib import Path

from aios_bench.publication import (
    PUBLICATION_SCHEMA,
    render_derived,
    verify_publication,
    write_publication_manifest,
)


SECRET_SENTINEL = "AIOS_BENCH_HIDDEN_ORACLE_SENTINEL_9f3e7c"


def _raw_run(root: Path) -> Path:
    directory = root / "piagent" / "ornith" / "runs" / "run-1"
    directory.mkdir(parents=True)
    (directory / "run.json").write_text(
        json.dumps({
            "harness": "piagent",
            "model": "ornith",
            "run_id": "run-1",
            "suite": "frontier_v3",
            "suite_revision": "rev",
            "status": "completed",
            "task_count": 1,
            "started_at": "2026-08-21T06:00:00Z",
            "finished_at": "2026-08-21T06:01:00Z",
            "execution_fingerprint": "profile",
        }),
        encoding="utf-8",
    )
    (directory / "results.jsonl").write_text(
        json.dumps({
            "task_id": "task-a",
            "task_revision": 1,
            "status": "completed",
            "success": True,
            "score": 100,
            "duration_seconds": 1.25,
            "telemetry_available": True,
            "category": "coding",
            "tier": 3,
            "evaluation": {
                "results": [{
                    "detail": SECRET_SENTINEL,
                    "hidden_oracle_value": SECRET_SENTINEL,
                }],
            },
            "agent_artifact_excerpt": SECRET_SENTINEL,
        }) + "\n",
        encoding="utf-8",
    )
    return directory


def _publish(raw: Path, published: Path) -> Path:
    render_derived(raw, published)
    return write_publication_manifest(raw, published)


def test_publication_seal_verifies_full_regeneration(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    published = tmp_path / "published"
    _raw_run(raw)

    manifest_path = _publish(raw, published)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = verify_publication(raw, published)

    assert manifest["schema"] == PUBLICATION_SCHEMA
    assert manifest["source"]["file_count"] == 2
    assert set(manifest["outputs"]) == {"summary.json", "dashboard.html"}
    assert result["ok"] is True
    assert result["errors"] == []
    assert result["actual_outputs"] == result["regenerated_outputs"]


def test_publication_does_not_transit_raw_oracle_or_artifact_payloads(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    published = tmp_path / "published"
    _raw_run(raw)

    manifest_path = _publish(raw, published)

    assert SECRET_SENTINEL in next(raw.rglob("results.jsonl")).read_text(encoding="utf-8")
    for path in (published / "summary.json", published / "dashboard.html", manifest_path):
        assert SECRET_SENTINEL not in path.read_text(encoding="utf-8")


def test_publication_verification_detects_tampered_derived_output(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    published = tmp_path / "published"
    _raw_run(raw)
    _publish(raw, published)

    summary = published / "summary.json"
    summary.write_text(summary.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    result = verify_publication(raw, published)

    assert result["ok"] is False
    assert any("output hash mismatch: summary.json" in error for error in result["errors"])
    assert any("not reproducible from raw inputs: summary.json" in error for error in result["errors"])


def test_publication_verification_detects_changed_raw_source(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    published = tmp_path / "published"
    directory = _raw_run(raw)
    _publish(raw, published)

    results = directory / "results.jsonl"
    results.write_text(
        results.read_text(encoding="utf-8")
        + json.dumps({
            "task_id": "task-a",
            "task_revision": 2,
            "status": "failed",
            "success": False,
            "score": 49,
            "duration_seconds": 2.0,
            "telemetry_available": True,
            "category": "coding",
            "tier": 3,
        })
        + "\n",
        encoding="utf-8",
    )
    result = verify_publication(raw, published)

    assert result["ok"] is False
    assert "raw source digest changed since publication" in result["errors"]
    assert "raw source file index changed since publication" in result["errors"]
    assert any("not reproducible from raw inputs" in error for error in result["errors"])


def test_publication_verification_fails_without_seal(tmp_path: Path) -> None:
    result = verify_publication(tmp_path / "raw", tmp_path / "published")
    assert result["ok"] is False
    assert result["errors"] == ["publication.json is missing"]
