from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .golden_solutions import materialize_parametric_golden as _legacy_materializer
from .tool_recovery_service import (
    ToolRecoveryError,
    ToolRecoveryService,
    tool_action_log_path,
)
from .world_service import (
    SupportDependencyWorldService,
    SupportWorldService,
    world_action_log_path,
)


def _write(workspace: Path, relative: str, content: str) -> None:
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _config_traversal_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    settings = oracle.get("settings") or {}
    chain = oracle.get("reference_chain") or []
    consumer = str(oracle.get("consumer_path", ""))
    if not isinstance(settings, Mapping) or not isinstance(chain, list):
        raise ValueError("invalid config traversal oracle")

    lines = ["# Effective configuration", ""]
    for key, value in settings.items():
        lines.append(f"{key}: {value}")
    lines.extend([
        "",
        "reference chain: " + " -> ".join(str(item) for item in chain),
        f"consumer: {consumer}",
        "",
    ])
    _write(workspace, "reports/effective_config.md", "\n".join(lines))
    return []


def _workspace_lineage_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    active_release = oracle.get("active_release")
    root = oracle.get("root")
    lineage_paths = oracle.get("lineage_paths")
    effective_settings = oracle.get("effective_settings")
    consumer_path = oracle.get("consumer_path")
    stale_sources = oracle.get("stale_source_paths")
    if (
        not isinstance(active_release, str)
        or not isinstance(root, str)
        or not isinstance(lineage_paths, list)
        or not isinstance(effective_settings, Mapping)
        or not isinstance(consumer_path, str)
        or not isinstance(stale_sources, list)
    ):
        raise ValueError("invalid workspace lineage oracle")

    payload = {
        "active_release": active_release,
        "root": root,
        "lineage_paths": lineage_paths,
        "effective_settings": dict(effective_settings),
        "consumer_path": consumer_path,
        "ignored_stale_sources": stale_sources,
    }
    _write(
        workspace,
        "reports/workspace_lineage.json",
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return []


def _wide_retrieval_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    query_id = oracle.get("query_id")
    target_rows = oracle.get("target_rows")
    if not isinstance(query_id, str) or not isinstance(target_rows, list):
        raise ValueError("invalid wide retrieval oracle")
    if not all(isinstance(row, Mapping) for row in target_rows):
        raise ValueError("invalid wide retrieval target rows")
    payload = {
        "query_id": query_id,
        "records": [dict(row) for row in target_rows],
    }
    _write(
        workspace,
        "reports/wide_retrieval.json",
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return []


def _cross_artifact_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    expected = oracle.get("expected")
    if not isinstance(expected, Mapping):
        raise ValueError("invalid cross-artifact oracle")
    groups = expected.get("groups")
    if not isinstance(groups, list) or not all(isinstance(row, Mapping) for row in groups):
        raise ValueError("invalid cross-artifact groups")

    payload = {
        "source": expected.get("source"),
        "groups": [dict(row) for row in groups],
        "posted_count": expected.get("posted_count"),
        "grand_total_cents": expected.get("grand_total_cents"),
    }
    _write(
        workspace,
        "reports/account_summary.json",
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )

    lines = [
        "# Account summary",
        "",
        f"source: {expected.get('source')}",
        "",
        "| account | posted_count | net_cents |",
        "| --- | ---: | ---: |",
    ]
    for row in groups:
        lines.append(
            f"| {row['account']} | {row['posted_count']} | {row['net_cents']} |"
        )
    lines.extend([
        "",
        f"posted_count: {expected.get('posted_count')}",
        f"grand_total_cents: {expected.get('grand_total_cents')}",
        "",
    ])
    _write(workspace, "reports/account_summary.md", "\n".join(lines))
    return []


def _epistemic_twins_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    source_path = oracle.get("source_path")
    result_path = oracle.get("result_path")
    expected = oracle.get("expected_decisions")
    if (
        not isinstance(source_path, str)
        or not isinstance(result_path, str)
        or not isinstance(expected, Mapping)
        or not all(isinstance(row, Mapping) for row in expected.values())
    ):
        raise ValueError("invalid epistemic-twins oracle")
    decisions = [dict(expected[case_id]) for case_id in sorted(expected)]
    _write(
        workspace,
        result_path,
        json.dumps(
            {"source": source_path, "decisions": decisions},
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n",
    )
    return []


def _black_box_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    spec = oracle.get("reference_spec")
    if not isinstance(spec, Mapping):
        raise ValueError("invalid black-box reconstruction oracle")
    encoded = json.dumps(dict(spec), sort_keys=True, separators=(",", ":"))
    source = f'''from __future__ import annotations

import json
import sys

SPEC = json.loads({encoded!r})


def transform(value):
    enabled = set(SPEC["enabled_rules"])
    units = int(value["units"])
    quantum = int(SPEC["round_quantum"])
    normalized = units
    if "quantize_units" in enabled and units:
        normalized = ((units + quantum - 1) // quantum) * quantum
    score = normalized
    if "plan_multiplier" in enabled:
        score *= int(SPEC["plan_multipliers"][value["plan"]])
    if "region_offset" in enabled:
        score += int(SPEC["region_offsets"][value["region"]])
    if "priority_weight" in enabled:
        score += int(value["priority"]) * int(SPEC["priority_weight"])
    if "active_adjustment" in enabled:
        score += int(SPEC["active_bonus"]) if value["active"] else -int(SPEC["inactive_penalty"])
    tags = set(value["tags"])
    if "tag_bonus" in enabled and SPEC["special_tag"] in tags:
        score += int(SPEC["special_tag_bonus"])
    if "bulk_bonus" in enabled and units >= int(SPEC["bulk_threshold"]):
        score += int(SPEC["bulk_bonus"])
    if "premium_bonus" in enabled and value["plan"] == SPEC["premium_plan"]:
        score += int(SPEC["premium_bonus"])
    score = max(0, int(score))
    low, high = (int(item) for item in SPEC["bucket_thresholds"])
    bucket = "low" if score < low else "standard" if score < high else "high"
    flags = []
    if not value["active"]:
        flags.append("inactive")
    if int(value["priority"]) >= int(SPEC["priority_flag_threshold"]):
        flags.append("priority")
    if "tag_bonus" in enabled and SPEC["special_tag"] in tags:
        flags.append("tag:" + str(SPEC["special_tag"]))
    if "bulk_bonus" in enabled and units >= int(SPEC["bulk_threshold"]):
        flags.append("bulk")
    if "premium_bonus" in enabled and value["plan"] == SPEC["premium_plan"]:
        flags.append("premium")
    return {{
        "bucket": bucket,
        "score": score,
        "normalized_units": normalized,
        "flags": sorted(flags),
    }}


for line in sys.stdin:
    if line.strip():
        print(json.dumps(transform(json.loads(line)), sort_keys=True, separators=(",", ":")))
'''
    _write(workspace, str(oracle.get("solution_path", "solution/reconstruct.py")), source)
    return []


def _persistent_memory_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    expected_memory = oracle.get("expected_memory")
    expected_report = oracle.get("expected_report")
    report_path = oracle.get("report_path")
    if (
        not isinstance(expected_memory, Mapping)
        or not isinstance(expected_report, Mapping)
        or not isinstance(report_path, str)
        or not report_path
    ):
        raise ValueError("invalid persistent-memory oracle")
    _write(
        workspace,
        ".agent_memory/preferences.json",
        json.dumps(
            dict(expected_memory),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n",
    )
    _write(
        workspace,
        report_path,
        json.dumps(
            dict(expected_report),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n",
    )
    return []


def _learning_transfer_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    expected_skill = oracle.get("expected_skill")
    expected_report = oracle.get("expected_report")
    report_path = oracle.get("report_path")
    if (
        not isinstance(expected_skill, Mapping)
        or not isinstance(expected_report, Mapping)
        or not isinstance(report_path, str)
        or not report_path
    ):
        raise ValueError("invalid learning-transfer oracle")
    _write(
        workspace,
        "skills/reporting_workflow.json",
        json.dumps(dict(expected_skill), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    _write(
        workspace,
        report_path,
        json.dumps(dict(expected_report), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return []


def _mediated_world_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path,
    task_id: str,
    service_class: type[SupportWorldService],
) -> list[dict[str, Any]]:
    database_path = str(oracle.get("database_path", ""))
    mutations = oracle.get("expected_mutations")
    target_ids = oracle.get("target_ids")
    if not database_path or not isinstance(mutations, Mapping) or not isinstance(target_ids, list):
        raise ValueError("invalid mediated world oracle")

    service = service_class(
        workspace / database_path,
        world_action_log_path(run_dir, task_id),
    )
    for index, ticket_id in enumerate(target_ids, 1):
        ticket = str(ticket_id)
        if not isinstance(mutations.get(ticket), Mapping):
            raise ValueError(f"missing mediated world mutation: {ticket}")
        service.escalate_ticket(ticket, f"golden-{index}-{ticket}")

    lines = ["# Escalation summary", ""]
    lines.extend(f"- {ticket_id}" for ticket_id in target_ids)
    lines.append("")
    _write(workspace, "reports/escalation_summary.md", "\n".join(lines))
    return []


def _tool_recovery_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path,
    task_id: str,
) -> list[dict[str, Any]]:
    state_path = str(oracle.get("state_path", ""))
    targets = oracle.get("target_ids")
    incomplete = oracle.get("incomplete_case_ids")
    ambiguous = {str(value) for value in (oracle.get("ambiguous_write_case_ids") or [])}
    if not state_path or not isinstance(targets, list) or not isinstance(incomplete, list):
        raise ValueError("invalid tool recovery oracle")

    service = ToolRecoveryService(
        workspace / state_path,
        tool_action_log_path(run_dir, task_id),
        oracle,
    )
    service.invoke("cases.list", {})
    for case_id in incomplete:
        arguments = {"case_id": str(case_id)}
        try:
            service.invoke("cases.get", arguments)
        except ToolRecoveryError as exc:
            if not exc.retryable:
                raise
            service.invoke("cases.get", arguments)

    for index, case_id in enumerate(targets, 1):
        case = str(case_id)
        arguments = {
            "case_id": case,
            "idempotency_key": f"golden-{index}-{case}",
        }
        try:
            service.invoke("actions.process", arguments)
        except ToolRecoveryError as exc:
            if not exc.retryable or case not in ambiguous:
                raise
            service.invoke("actions.process", arguments)

    payload = {
        "processed_case_ids": [str(value) for value in targets],
        "recovered_case_ids": sorted(ambiguous),
    }
    _write(
        workspace,
        "reports/tool_recovery_summary.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )
    return []


def materialize_parametric_golden(
    family: str,
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None = None,
    task_id: str | None = None,
) -> list[dict[str, Any]]:
    services: dict[str, type[SupportWorldService]] = {
        "stateful_world": SupportWorldService,
        "dependency_world": SupportDependencyWorldService,
    }
    service_class = services.get(family)
    if service_class is not None:
        if run_dir is None or not task_id:
            raise ValueError(f"{family} golden requires run_dir and task_id")
        return _mediated_world_golden(
            workspace,
            oracle,
            run_dir=run_dir,
            task_id=task_id,
            service_class=service_class,
        )
    if family == "tool_recovery":
        if run_dir is None or not task_id:
            raise ValueError("tool_recovery golden requires run_dir and task_id")
        return _tool_recovery_golden(
            workspace,
            oracle,
            run_dir=run_dir,
            task_id=task_id,
        )
    if family == "config_traversal":
        return _config_traversal_golden(workspace, oracle)
    if family == "workspace_lineage":
        return _workspace_lineage_golden(workspace, oracle)
    if family == "wide_retrieval":
        return _wide_retrieval_golden(workspace, oracle)
    if family == "cross_artifact":
        return _cross_artifact_golden(workspace, oracle)
    if family == "epistemic_twins":
        return _epistemic_twins_golden(workspace, oracle)
    if family == "black_box_reconstruction":
        return _black_box_golden(workspace, oracle)
    if family == "persistent_memory":
        return _persistent_memory_golden(workspace, oracle)
    if family == "learning_transfer":
        return _learning_transfer_golden(workspace, oracle)
    return _legacy_materializer(family, workspace, oracle)


__all__ = ["materialize_parametric_golden"]