from __future__ import annotations

from dataclasses import dataclass, field

from .adapters import ADAPTERS, Adapter, CapabilityAssessment


BENCHMARK_LOCAL_RUNTIME = "benchmark_local_runtime"


@dataclass(frozen=True)
class AgentConfig:
    name: str
    display_name: str
    adapter: Adapter
    runtime_capabilities: frozenset[str] = field(default_factory=frozenset)

    def assess_task(self, task: object) -> CapabilityAssessment:
        base = self.adapter.assess_task(task)
        supported = base.supported.union(self.runtime_capabilities)
        return CapabilityAssessment(
            required=base.required,
            supported=supported,
            missing=base.required.difference(supported),
        )


_DISPLAY_NAMES = {
    "hermes": "Hermes Agent",
    "piagent": "Pi Agent",
    "opencode": "OpenCode",
    "goose": "Goose",
    "letta": "Letta",
    "agentzero": "Agent Zero",
    "claude": "Claude Code",
}

# These harnesses execute their workspace tools on the benchmark host and can
# therefore reach task-scoped loopback services. Agent Zero executes tools in
# an external service/project and needs a separate bridge before this contract
# can be considered comparable.
_LOCAL_RUNTIME_HARNESSES = frozenset(_DISPLAY_NAMES).difference({"agentzero"})

ACTIVE_HARNESS_NAMES = tuple(_DISPLAY_NAMES)
AGENTS = {
    name: AgentConfig(
        name,
        _DISPLAY_NAMES[name],
        ADAPTERS[name],
        frozenset({BENCHMARK_LOCAL_RUNTIME}) if name in _LOCAL_RUNTIME_HARNESSES else frozenset(),
    )
    for name in ACTIVE_HARNESS_NAMES
}
