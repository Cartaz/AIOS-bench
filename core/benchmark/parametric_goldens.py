from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .golden_solutions import materialize_parametric_golden as _legacy_materializer
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
    if family == "config_traversal":
        return _config_traversal_golden(workspace, oracle)
    return _legacy_materializer(family, workspace, oracle)


__all__ = ["materialize_parametric_golden"]
