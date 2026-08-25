from core.benchmark import config, harness_registry, runner


def test_harness_registry_has_one_canonical_owner() -> None:
    assert config.AGENTS is harness_registry.AGENTS
    assert runner.AGENTS is harness_registry.AGENTS
    assert config.AgentConfig is harness_registry.AgentConfig
    assert runner.AgentConfig is harness_registry.AgentConfig
    assert tuple(harness_registry.AGENTS) == harness_registry.ACTIVE_HARNESS_NAMES
