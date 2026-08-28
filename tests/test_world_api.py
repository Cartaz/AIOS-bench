from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path

import pytest

from aios_bench.parametric import materialize_variant
from aios_bench.world_api import SupportWorldService, WorldAPIError


def test_support_world_service_has_typed_reads_and_idempotent_write(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("stateful_world", workspace, seed=88)
    log = tmp_path / "hidden" / "actions.jsonl"
    service = SupportWorldService(workspace / oracle["database_path"], log)

    tickets = service.list_tickets()
    assert [row["id"] for row in tickets] == sorted(row["id"] for row in tickets)
    target = oracle["target_ids"][0]
    before = service.get_ticket(target)
    assert before["priority"] == "normal"

    first = service.escalate_ticket(target, "stable-key")
    replay = service.escalate_ticket(target, "stable-key")
    assert first["changed"] is True
    assert first["idempotent_replay"] is False
    assert replay["changed"] is True
    assert replay["idempotent_replay"] is True

    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["sequence"] == 1
    assert records[0]["before"] == before
    assert records[0]["after"]["priority"] == "urgent"


def test_support_world_service_rejects_idempotency_reuse_for_another_action(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("stateful_world", workspace, seed=89)
    service = SupportWorldService(
        workspace / oracle["database_path"],
        tmp_path / "hidden" / "actions.jsonl",
    )
    first, second = oracle["target_ids"][:2]
    service.escalate_ticket(first, "same-key")

    with pytest.raises(WorldAPIError) as exc:
        service.escalate_ticket(second, "same-key")
    assert exc.value.status == HTTPStatus.CONFLICT
    assert exc.value.code == "idempotency_conflict"


def test_support_world_service_rejects_unknown_ticket_with_stable_error(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("stateful_world", workspace, seed=90)
    service = SupportWorldService(
        workspace / oracle["database_path"],
        tmp_path / "hidden" / "actions.jsonl",
    )

    with pytest.raises(WorldAPIError) as exc:
        service.get_ticket("TKT-9999")
    assert exc.value.status == HTTPStatus.NOT_FOUND
    assert exc.value.code == "ticket_not_found"
    assert str(exc.value) == "ticket does not exist"
