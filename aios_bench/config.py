from pathlib import Path

# Compatibility facade for callers that imported the old configuration module.
# Keep the runner registry as the source of adapter definitions, but expose only
# the harnesses that belong to the benchmark matrix.
from .runner import AGENTS as _REGISTERED_AGENTS, AgentConfig

ACTIVE_HARNESS_NAMES = (
    "hermes",
    "piagent",
    "opencode",
    "goose",
    "letta",
    "agentzero",
)

AGENTS = {name: _REGISTERED_AGENTS[name] for name in ACTIVE_HARNESS_NAMES}
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
