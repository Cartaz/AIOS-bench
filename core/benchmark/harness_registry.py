from __future__ import annotations

from dataclasses import dataclass

from .adapters import ADAPTERS, Adapter


@dataclass(frozen=True)
class AgentConfig:
    name: str
    display_name: str
    adapter: Adapter


_DISPLAY_NAMES = {
    "hermes": "Hermes Agent",
    "piagent": "Pi Agent",
    "opencode": "OpenCode",
    "goose": "Goose",
    "letta": "Letta",
    "agentzero": "Agent Zero",
    "claude": "Claude Code",
}

ACTIVE_HARNESS_NAMES = tuple(_DISPLAY_NAMES)
AGENTS = {
    name: AgentConfig(name, _DISPLAY_NAMES[name], ADAPTERS[name])
    for name in ACTIVE_HARNESS_NAMES
}
