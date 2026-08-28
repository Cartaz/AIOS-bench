from __future__ import annotations

from types import SimpleNamespace

from aios_bench.config import AGENTS
from aios_bench.adapters import PiAgentAdapter


def _runtime_task():
    return SimpleNamespace(
        category="autonomy",
        tags=(),
        required_capabilities=("benchmark_local_runtime",),
    )


def test_local_harnesses_support_benchmark_owned_loopback_runtime() -> None:
    task = _runtime_task()
    for name in ("hermes", "piagent", "opencode", "goose", "letta", "claude"):
        assessment = AGENTS[name].adapter.assess_task(task)
        assert assessment.is_supported, (name, assessment.missing)
        assert "benchmark_local_runtime" in assessment.supported


def test_remote_agentzero_is_explicitly_unsupported_until_runtime_bridge_exists() -> None:
    assessment = AGENTS["agentzero"].adapter.assess_task(_runtime_task())
    assert assessment.is_supported is False
    assert assessment.missing == frozenset({"benchmark_local_runtime"})


def test_configured_pi_adapter_preserves_concrete_rpc_dispatch_type() -> None:
    assert isinstance(AGENTS["piagent"].adapter, PiAgentAdapter)
