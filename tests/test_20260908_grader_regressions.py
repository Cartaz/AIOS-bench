from __future__ import annotations

import copy
import json
from pathlib import Path

from aios_bench.parametric import evaluate_variant, materialize_variant
from aios_bench.parametric.cross_artifact import grade_cross_artifact_variant
from aios_bench.parametric_goldens import materialize_parametric_golden


def _write_config_table(workspace: Path, oracle: dict, *, boundary_pipes: bool) -> None:
    lines = ["# Effective configuration", ""]
    if boundary_pipes:
        lines.extend(["| setting | value |", "| --- | --- |"])
        lines.extend(
            f"| {key} | {value} |" for key, value in oracle["settings"].items()
        )
    else:
        lines.extend(["setting | value", "--- | ---"])
        lines.extend(
            f"{key} | {value}" for key, value in oracle["settings"].items()
        )
    lines.extend(
        [
            "",
            "reference chain: " + " -> ".join(oracle["reference_chain"]),
            f"consumer: {oracle['consumer_path']}",
        ]
    )
    (workspace / "reports" / "effective_config.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _write_cross_artifacts(
    workspace: Path,
    expected: dict,
    *,
    boundary_pipes: bool,
) -> None:
    reports = workspace / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "account_summary.json").write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if boundary_pipes:
        header = "| account | posted_count | net_cents |"
        separator = "| --- | ---: | ---: |"
        rows = [
            f"| {row['account']} | {row['posted_count']} | {row['net_cents']} |"
            for row in expected["groups"]
        ]
    else:
        header = "account | posted_count | net_cents"
        separator = "--- | ---: | ---:"
        rows = [
            f"{row['account']} | {row['posted_count']} | {row['net_cents']}"
            for row in expected["groups"]
        ]
    lines = [
        "# Account summary",
        "",
        f"source: {expected['source']}",
        "",
        header,
        separator,
        *rows,
        "",
        f"posted_count: {expected['posted_count']}",
        f"grand_total_cents: {expected['grand_total_cents']}",
        "",
    ]
    (reports / "account_summary.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def test_config_markdown_table_is_semantically_accepted(tmp_path: Path) -> None:
    for boundary_pipes in (True, False):
        workspace = tmp_path / str(boundary_pipes)
        oracle = materialize_variant("config_traversal", workspace, seed=1050196802)
        _write_config_table(workspace, oracle, boundary_pipes=boundary_pipes)

        grade = evaluate_variant("config_traversal", workspace, oracle)

        assert grade.passed is True, grade.detail
        assert grade.score == 1.0


def test_config_partial_credit_uses_table_values(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("config_traversal", workspace, seed=1050196802)
    _write_config_table(workspace, oracle, boundary_pipes=True)
    report = workspace / "reports" / "effective_config.md"
    first_key = next(iter(oracle["settings"]))
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            f"| {first_key} | {oracle['settings'][first_key]} |",
            f"| {first_key} | wrong |",
        ),
        encoding="utf-8",
    )

    grade = evaluate_variant("config_traversal", workspace, oracle)

    assert grade.passed is False
    assert 0.0 < grade.metrics["settings_accuracy"] < 1.0
    assert grade.score > 0.5


def test_cross_artifact_accepts_gfm_table_without_boundary_pipes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("cross_artifact", workspace, seed=1604958177)
    _write_cross_artifacts(
        workspace,
        copy.deepcopy(oracle["expected"]),
        boundary_pipes=False,
    )

    grade = grade_cross_artifact_variant(workspace, oracle)

    assert grade.passed is True, grade.detail
    assert grade.score == 1.0


def test_persistent_memory_capture_documents_canonical_schema(tmp_path: Path) -> None:
    oracle = materialize_variant(
        "persistent_memory",
        tmp_path,
        seed=65125655,
        context={"phase": "capture", "state_scope": "persistent_memory_v1"},
    )

    schema_doc = tmp_path / "docs" / "memory_schema.md"
    assert schema_doc.is_file()
    text = schema_doc.read_text(encoding="utf-8")
    assert oracle["expected_memory"]["schema"] in text
    assert "preferences" in text
    assert "history" in text


def test_persistent_memory_noncanonical_semantic_state_gets_partial_credit(
    tmp_path: Path,
) -> None:
    oracle = materialize_variant(
        "persistent_memory",
        tmp_path,
        seed=65125655,
        context={"phase": "capture", "state_scope": "persistent_memory_v1"},
    )
    materialize_parametric_golden("persistent_memory", tmp_path, oracle)
    expected = oracle["expected_memory"]
    alternative = {
        "schema": "aios-bench/preference-source/v1",
        "authority": "current",
        "durability_filter": "durable",
        "preferences": expected["preferences"],
    }
    (tmp_path / ".agent_memory" / "preferences.json").write_text(
        json.dumps(alternative),
        encoding="utf-8",
    )

    grade = evaluate_variant("persistent_memory", tmp_path, oracle)

    assert grade.passed is False
    assert 0.85 <= grade.score < 1.0
    assert grade.metrics["preference_accuracy"] == 1.0
    assert grade.metrics["history_accuracy"] == 1.0
    assert grade.metrics["schema_conformity"] == 0.0
    assert grade.metrics["report_accuracy"] == 1.0


def test_persistent_memory_capture_report_list_order_is_not_semantic(
    tmp_path: Path,
) -> None:
    oracle = materialize_variant(
        "persistent_memory",
        tmp_path,
        seed=65125655,
        context={"phase": "capture", "state_scope": "persistent_memory_v1"},
    )
    materialize_parametric_golden("persistent_memory", tmp_path, oracle)
    report_path = tmp_path / oracle["report_path"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["stored_keys"].reverse()
    report["excluded_transient_keys"].reverse()
    report_path.write_text(json.dumps(report), encoding="utf-8")

    grade = evaluate_variant("persistent_memory", tmp_path, oracle)

    assert grade.passed is True, grade.detail
    assert grade.score == 1.0
