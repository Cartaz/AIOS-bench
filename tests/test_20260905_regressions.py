from __future__ import annotations

import json
from pathlib import Path

from aios_bench.parametric import materialize_variant
from aios_bench.parametric.cross_artifact import grade_cross_artifact_variant
from aios_bench.tasks import load_tasks


ROOT = Path(__file__).resolve().parents[1]


def test_cross_artifact_accepts_valid_unaligned_markdown_separator(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("cross_artifact", workspace, seed=42)
    expected = oracle["expected"]
    reports = workspace / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "account_summary.json").write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Account summary",
        "",
        f"source: {expected['source']}",
        "",
        "| account | posted_count | net_cents |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| {row['account']} | {row['posted_count']} | {row['net_cents']} |"
        for row in expected["groups"]
    )
    lines.extend([
        "",
        f"posted_count: {expected['posted_count']}",
        f"grand_total_cents: {expected['grand_total_cents']}",
        "",
    ])
    (reports / "account_summary.md").write_text("\n".join(lines), encoding="utf-8")

    grade = grade_cross_artifact_variant(workspace, oracle)

    assert grade.passed is True
    assert grade.score == 1.0


def test_escalation_tasks_make_exact_report_id_contract_explicit() -> None:
    tasks = {
        task.id: task
        for task in load_tasks(ROOT / "benchmarks" / "tasks", "frontier_v4")
    }

    stateful = tasks["stateful_support_001"]
    dependency = tasks["support_dependency_001"]
    assert stateful.revision == 6
    assert dependency.revision == 5
    for task in (stateful, dependency):
        assert "exact changed-ticket manifest" in task.prompt
        assert "do not mention identifiers of unchanged tickets" in task.prompt
