from __future__ import annotations

from .harness_registry import ACTIVE_HARNESS_NAMES, AGENTS, AgentConfig

Harness = AgentConfig
DEFAULT_HARNESSES = AGENTS

__all__ = [
    "ACTIVE_HARNESS_NAMES",
    "AGENTS",
    "AgentConfig",
    "DEFAULT_HARNESSES",
    "Harness",
]
