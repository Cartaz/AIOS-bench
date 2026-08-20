from __future__ import annotations

from pathlib import Path

# Compatibility facade for callers that imported the old configuration module.
# The runner registry is authoritative; keeping a second list here previously
# allowed supported harnesses and commands to drift out of sync.
from .runner import AGENTS, AgentConfig

Harness = AgentConfig
DEFAULT_HARNESSES = AGENTS


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def fixture_root() -> Path:
    return repo_root() / "benchmarks" / "fixtures" / "workspace"


def results_root() -> Path:
    return repo_root() / "results" / ".local"


def published_results_root() -> Path:
    return repo_root() / "results"
