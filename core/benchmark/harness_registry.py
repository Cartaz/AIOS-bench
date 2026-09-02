from __future__ import annotations

from dataclasses import dataclass, field

from .adapters import ADAPTERS, Adapter, CapabilityAssessment
from .deepseek_adapter import DeepSeekHarnessAdapter


BENCHMARK_LOCAL_RUNTIME = "benchmark_local_runtime"


@dataclass(frozen=True)
class AgentConfig:
    name: str
    display_name: str
    adapter: Adapter
    runtime_capabilities: frozenset[str] = field(default_factory=frozenset)

    def assess_task(self, task: object) -> CapabilityAssessment:
        return self.adapter.assess_task(task)


_DISPLAY_NAMES = {
    "hermes": "Hermes Agent",
    "piagent": "Pi Agent",
    "opencode": "OpenCode",
    "goose": "Goose",
    "letta": "Letta",
    "agentzero": "Agent Zero",
    "claude": "Claude Code",
    "deepseek": "DeepSeek Harness",
}

_ADAPTER_SOURCES: dict[str, Adapter] = {
    **ADAPTERS,
    "deepseek": DeepSeekHarnessAdapter(),
}

# These harnesses execute workspace tools on the benchmark host and can reach
# task-scoped loopback services. Agent Zero executes tools in an external
# service/project and needs a separate bridge before this contract is fair.
_LOCAL_RUNTIME_HARNESSES = frozenset(_DISPLAY_NAMES).difference({"agentzero"})


def _configured_adapter(name: str, runtime_capabilities: frozenset[str]) -> Adapter:
    """Clone the stateless adapter and bind capabilities of this deployment.

    Existing runner code deliberately asks the configured adapter for task
    support. Cloning keeps deployment-only capabilities out of the canonical
    adapter sources while preserving concrete adapter types (notably the Pi RPC
    isinstance dispatch).
    """

    source = _ADAPTER_SOURCES[name]
    adapter = type(source)()
    adapter.capabilities = source.capabilities.union(runtime_capabilities)
    return adapter


ACTIVE_HARNESS_NAMES = tuple(_DISPLAY_NAMES)
AGENTS = {}
for name in ACTIVE_HARNESS_NAMES:
    runtime_capabilities = (
        frozenset({BENCHMARK_LOCAL_RUNTIME})
        if name in _LOCAL_RUNTIME_HARNESSES
        else frozenset()
    )
    AGENTS[name] = AgentConfig(
        name,
        _DISPLAY_NAMES[name],
        _configured_adapter(name, runtime_capabilities),
        runtime_capabilities,
    )
