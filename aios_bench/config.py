from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Harness:
    name: str
    display_name: str
    command: str
    description: str = ""


DEFAULT_HARNESSES = {
    "hermes": Harness("hermes", "Hermes Agent", "hermes"),
    "piagent": Harness("piagent", "Pi Agent", "pi"),
    "opencode": Harness("opencode", "OpenCode", "opencode"),
    "goose": Harness("goose", "Goose", "goose"),
    "letta": Harness("letta", "Letta", "letta"),
    "agentzero": Harness("agentzero", "Agent Zero", "agent-zero"),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def fixture_root() -> Path:
    return repo_root() / "benchmarks" / "fixtures" / "workspace"


def results_root() -> Path:
    return repo_root() / "results"
