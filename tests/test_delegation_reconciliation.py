from __future__ import annotations

from pathlib import Path

from aios_bench.adapters import required_capabilities_for
from aios_bench.config import AGENTS
from aios_bench.evaluators import evaluate_artifacts
from aios_bench.parametric import evaluate_variant, materialize_variant
from aios_bench.parametric_goldens import materialize_parametric_golden


SUPPORTED_DELEGATION_HARNESSES = {"opencode", "goose", "letta", "agentzero", "claude"}


def _events(*, nested: bool = False, second_error: bool = False):
    result = []
    for index in (1, 2):
        payload = {"call_id": f"call-{index}", "inferred": False}
        if nested:
            payload = {"payload": {"id": f"call-{index}", "inferred": False}}
        result.append({"type": "subagent_start", "source": "test", "data": payload})
        end_payload = {"call_id": f"call-{index}", "inferred": False, "is_error": second_error and index == 2}
        if nested:
            end_payload = {"payload": {"id": f"call-{index}", "inferred": False, "is_error": second_error and index == 2}}
        result.append({"type": "subagent_end", "source": "test", "data": end_payload})
    return result


def test_delegation_capability_is_observable_only_on_supported_harnesses() -> None:
    assert required_capabilities_for("subagents") == frozenset({"structured_subagent_events"})
    supported = {
        name for name, agent in AGENTS.items()
        if agent.adapter.assess_capabilities("subagents").is_supported
    }
    assert supported == SUPPORTED_DELEGATION_HARNESSES


def test_structured_delegation_requires_completed_distinct_non_inferred_lifecycles(tmp_path: Path) -> None:
    checks = [{
        "type": "structured_delegation",
        "min_starts": 2,
        "min_completed": 2,
        "require_unique_ids": True,
        "weight": 1,
        "fatal": True,
    }]
    assert evaluate_artifacts(tmp_path, checks, events=_events())["passed"] is True
    assert evaluate_artifacts(tmp_path, checks, events=_events(nested=True))["passed"] is True
    assert evaluate_artifacts(tmp_path, checks, events=_events(second_error=True))["passed"] is False
    inferred = _events()
    inferred[0]["data"]["inferred"] = True
    assert evaluate_artifacts(tmp_path, checks, events=inferred)["passed"] is False


def test_delegation_content_is_seeded_strict_and_golden_is_observable(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    oracle_a = materialize_variant("delegation_reconciliation", first, seed=123)
    oracle_b = materialize_variant("delegation_reconciliation", second, seed=123)
    assert oracle_a["variant_digest"] == oracle_b["variant_digest"]
    assert oracle_a["expected_report"] == oracle_b["expected_report"]

    events = materialize_parametric_golden("delegation_reconciliation", first, oracle_a)
    assert len([event for event in events if event["type"] == "subagent_start"]) == 2
    assert evaluate_variant("delegation_reconciliation", first, oracle_a).passed is True

    report = first / "reports" / "delegation_reconciliation.json"
    report.write_text('{"topics": []}\n', encoding="utf-8")
    assert evaluate_variant("delegation_reconciliation", first, oracle_a).passed is False
