from __future__ import annotations

import json
from pathlib import Path

from aios_bench.parametric import (
    WorkspaceLineagePressure,
    check_variant,
    materialize_variant,
)


def _write_valid_report(workspace: Path, oracle: dict) -> None:
    payload = {
        "active_release": oracle["active_release"],
        "root": oracle["root"],
        "lineage_paths": oracle["lineage_paths"],
        "effective_settings": oracle["effective_settings"],
        "consumer_path": oracle["consumer_path"],
        "ignored_stale_sources": oracle["stale_source_paths"],
    }
    path = workspace / "reports" / "workspace_lineage.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _source_identity(relative: str) -> tuple[str, int]:
    name = Path(relative).name.removesuffix(".json")
    node_id, revision = name.rsplit(".r", 1)
    return node_id, int(revision)


def test_workspace_lineage_is_deterministic_for_same_seed(tmp_path: Path) -> None:
    pressure = WorkspaceLineagePressure(
        lineage_depth=5,
        branch_count=4,
        stale_revisions=3,
        distractor_files=6,
        extra_settings=3,
    )
    first = materialize_variant(
        "workspace_lineage",
        tmp_path / "first",
        seed=2026,
        parameters=pressure.to_dict(),
    )
    second = materialize_variant(
        "workspace_lineage",
        tmp_path / "second",
        seed=2026,
        parameters=pressure.to_dict(),
    )

    assert first["variant_digest"] == second["variant_digest"]
    assert first["protected_sha256"] == second["protected_sha256"]
    assert first["lineage_paths"] == second["lineage_paths"]
    assert first["effective_settings"] == second["effective_settings"]


def test_workspace_lineage_changes_with_seed_or_pressure(tmp_path: Path) -> None:
    baseline = materialize_variant("workspace_lineage", tmp_path / "a", seed=41)
    other_seed = materialize_variant("workspace_lineage", tmp_path / "b", seed=42)
    other_pressure = materialize_variant(
        "workspace_lineage",
        tmp_path / "c",
        seed=41,
        parameters={
            "lineage_depth": 6,
            "branch_count": 4,
            "stale_revisions": 3,
            "distractor_files": 7,
            "extra_settings": 4,
        },
    )

    assert baseline["variant_digest"] != other_seed["variant_digest"]
    assert baseline["variant_digest"] != other_pressure["variant_digest"]


def test_workspace_lineage_materializes_revision_pinned_dag(tmp_path: Path) -> None:
    pressure = WorkspaceLineagePressure(
        lineage_depth=6,
        branch_count=4,
        stale_revisions=2,
        distractor_files=3,
        extra_settings=2,
    )
    workspace = tmp_path / "workspace"
    oracle = materialize_variant(
        "workspace_lineage",
        workspace,
        seed=77,
        parameters=pressure.to_dict(),
    )

    paths = oracle["lineage_paths"]
    assert len(paths) == pressure.branch_count
    assert all(len(path) == pressure.lineage_depth for path in paths)
    assert all(path[0] == oracle["root"] for path in paths)
    assert len({path[-1] for path in paths}) == 1
    assert all("@" in node for path in paths for node in path)
    assert len(oracle["stale_source_paths"]) == (
        pressure.stale_revisions
        * (2 + pressure.branch_count * (pressure.lineage_depth - 2))
    )
    assert all(path.startswith("config/sources/") for path in oracle["stale_source_paths"])
    assert not any("current" in path or "history" in path for path in oracle["stale_source_paths"])

    current = dict(_source_identity(path) for path in oracle["current_source_paths"])
    inactive = [_source_identity(path) for path in oracle["stale_source_paths"]]
    assert any(revision > current[node_id] for node_id, revision in inactive)
    assert any(revision < current[node_id] for node_id, revision in inactive)


def test_workspace_lineage_accepts_exact_grounded_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("workspace_lineage", workspace, seed=123)
    _write_valid_report(workspace, oracle)

    passed, detail = check_variant("workspace_lineage", workspace, oracle)

    assert passed is True, detail


def test_workspace_lineage_rejects_stale_revision_substitution(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("workspace_lineage", workspace, seed=1234)
    _write_valid_report(workspace, oracle)
    report_path = workspace / "reports" / "workspace_lineage.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    current = report["lineage_paths"][0][1]
    node_id, revision = current.rsplit("@", 1)
    report["lineage_paths"][0][1] = f"{node_id}@{int(revision) + 1}"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    passed, detail = check_variant("workspace_lineage", workspace, oracle)

    assert passed is False
    assert "lineage paths" in detail


def test_workspace_lineage_rejects_decoy_setting(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("workspace_lineage", workspace, seed=222)
    _write_valid_report(workspace, oracle)
    report_path = workspace / "reports" / "workspace_lineage.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    decoy_path = workspace / oracle["distractor_paths"][0]
    decoy = json.loads(decoy_path.read_text(encoding="utf-8"))
    report["effective_settings"].update(decoy["settings"])
    report_path.write_text(json.dumps(report), encoding="utf-8")

    passed, detail = check_variant("workspace_lineage", workspace, oracle)

    assert passed is False
    assert "effective settings" in detail


def test_workspace_lineage_rejects_incomplete_stale_inventory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("workspace_lineage", workspace, seed=333)
    _write_valid_report(workspace, oracle)
    report_path = workspace / "reports" / "workspace_lineage.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["ignored_stale_sources"] = report["ignored_stale_sources"][:-1]
    report_path.write_text(json.dumps(report), encoding="utf-8")

    passed, detail = check_variant("workspace_lineage", workspace, oracle)

    assert passed is False
    assert "stale lineage source inventory" in detail


def test_workspace_lineage_rejects_source_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("workspace_lineage", workspace, seed=444)
    _write_valid_report(workspace, oracle)
    source = workspace / oracle["current_source_paths"][0]
    source.write_text(source.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")

    passed, detail = check_variant("workspace_lineage", workspace, oracle)

    assert passed is False
    assert "protected source modified" in detail
