from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


UNKNOWN_MODEL_VALUES = frozenset({"", "unknown"})

# These are hard comparability requirements, not a taxonomy of everything a
# task happens to exercise.  Only categories which cannot be evaluated fairly
# without a harness-level facility belong here.  Other categories use the
# benchmark-owned workspace and deterministic oracle shared by every adapter.
REQUIRED_CAPABILITIES_BY_CATEGORY: dict[str, frozenset[str]] = {
    "browser": frozenset({"browser"}),
    "subagents": frozenset({"structured_subagent_events"}),
}


def _requested_model(model: str) -> str | None:
    return model if model and model not in UNKNOWN_MODEL_VALUES else None


@dataclass(frozen=True)
class AgentInvocation:
    command: list[str]
    environment: dict[str, str]
    requested_model: str | None = None
    resolved_model: str | None = None
    provider: str | None = None
    endpoint: str | None = None
    configuration: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityAssessment:
    """Result of checking one task against an adapter's hard requirements."""

    required: frozenset[str]
    supported: frozenset[str]
    missing: frozenset[str]

    @property
    def is_supported(self) -> bool:
        return not self.missing

    @property
    def status(self) -> str:
        return "supported" if self.is_supported else "unsupported"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "required": sorted(self.required),
            "supported": sorted(self.supported),
            "missing": sorted(self.missing),
        }


def required_capabilities_for(
    category: str,
    tags: Iterable[str] = (),
    explicit: Iterable[str] = (),
) -> frozenset[str]:
    """Return hard harness requirements for a catalog task.

    Catalogs may add ``requires:<capability>`` tags without requiring another
    runner change.  Category requirements remain deliberately conservative so
    ordinary benchmark skills are not confused with harness integration APIs.
    """

    required = set(REQUIRED_CAPABILITIES_BY_CATEGORY.get(category, ()))
    if isinstance(explicit, str):
        required.add(explicit)
    else:
        required.update(explicit)
    if isinstance(tags, str):
        tags = (tags,)
    for tag in tags:
        if tag.startswith("requires:") and tag.removeprefix("requires:"):
            required.add(tag.removeprefix("requires:"))
    return frozenset(required)


class Adapter:
    name: str
    capabilities: frozenset[str] = frozenset()

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        raise NotImplementedError

    def parse_event(self, line: str) -> dict | None:
        return None

    def assess_capabilities(
        self,
        category: str,
        tags: Iterable[str] = (),
        explicit: Iterable[str] = (),
    ) -> CapabilityAssessment:
        required = required_capabilities_for(category, tags, explicit)
        return CapabilityAssessment(
            required=required,
            supported=self.capabilities,
            missing=required.difference(self.capabilities),
        )

    def supports(self, required: Iterable[str]) -> bool:
        requirements = {required} if isinstance(required, str) else frozenset(required)
        return not requirements.difference(self.capabilities)

    def assess_task(self, task: object) -> CapabilityAssessment:
        """Assess a Task-like object without coupling adapters to catalog models."""

        return self.assess_capabilities(
            str(getattr(task, "category")),
            getattr(task, "tags", ()),
            getattr(task, "required_capabilities", ()),
        )


class HermesAdapter(Adapter):
    name = "hermes"
    capabilities = frozenset({"memory", "skills", "delegation", "terminal", "browser", "sessions"})

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["hermes", "chat", "--quiet"]
        if model and model != "unknown":
            command += ["--model", model]
        command += ["-q", prompt]
        requested = _requested_model(model)
        return AgentInvocation(
            command,
            {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())},
            requested_model=requested,
            resolved_model=requested,
            configuration={"mode": "chat", "quiet": True},
        )


class PiAgentAdapter(Adapter):
    name = "piagent"
    capabilities = frozenset({"json_events", "rpc", "sessions", "extensions", "tool_events", "token_stats"})

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        # Kept as a conventional invocation for discovery/backwards compatibility.
        # The runner uses run_rpc() so stdin remains open until agent_settled.
        command = ["pi", "--mode", "rpc", "--no-session"]
        if model and model != "unknown":
            command += ["--model", model]
        requested = _requested_model(model)
        return AgentInvocation(
            command,
            {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())},
            requested_model=requested,
            resolved_model=requested,
            configuration={"mode": "rpc", "session": "disabled"},
        )


class OpenCodeAdapter(Adapter):
    name = "opencode"
    capabilities = frozenset({
        "json_events",
        "sessions",
        "server",
        "mcp",
        "token_stats",
        "tool_events",
        "structured_subagent_events",
    })

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["opencode", "run", "--dir", str(workspace.resolve()), "--format", "json", "--auto"]
        if model and model != "unknown":
            command += ["--model", model]
        command.append(prompt)
        requested = _requested_model(model)
        return AgentInvocation(
            command,
            {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())},
            requested_model=requested,
            resolved_model=requested,
            configuration={"format": "json", "auto": True, "structured_task_tool": True},
        )


class GooseAdapter(Adapter):
    name = "goose"
    capabilities = frozenset({"recipes", "extensions", "sessions", "provider_model"})

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["goose", "run", "--no-session"]
        provider = os.environ.get("AIOS_BENCH_GOOSE_PROVIDER")
        if provider:
            command += ["--provider", provider]
        if model and model != "unknown":
            command += ["--model", model]
        command += ["-t", prompt]
        requested = _requested_model(model)
        return AgentInvocation(
            command,
            {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())},
            requested_model=requested,
            resolved_model=requested,
            provider=provider,
            configuration={"session": "disabled"},
        )


class LettaAdapter(Adapter):
    name = "letta"
    capabilities = frozenset({"memory", "skills", "subagents", "longitudinal", "headless", "sessions"})

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["letta", "-p"]
        agent_id = os.environ.get("AIOS_BENCH_LETTA_AGENT")
        if agent_id:
            command += ["--agent", agent_id]
        environment = {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())}
        if model and model != "unknown":
            environment["AIOS_BENCH_REQUESTED_MODEL"] = model
        requested = _requested_model(model)
        return AgentInvocation(
            command + [prompt],
            environment,
            requested_model=requested,
            # Letta resolves the model from the configured agent, not this CLI.
            resolved_model=None,
            configuration={"headless": True, "agent_id_configured": bool(agent_id)},
        )


class AgentZeroAdapter(Adapter):
    name = "agentzero"
    capabilities = frozenset({"memory", "knowledge", "projects", "api", "persistent_state"})

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["python", "-m", "aios_bench.agentzero_client", prompt]
        environment = {
            "AIOS_BENCH_WORKSPACE": str(workspace.resolve()),
            "AIOS_BENCH_AGENTZERO_URL": os.environ.get("AIOS_BENCH_AGENTZERO_URL", "http://127.0.0.1:80"),
            "AIOS_BENCH_AGENTZERO_API_KEY": os.environ.get("AIOS_BENCH_AGENTZERO_API_KEY", ""),
        }
        project = os.environ.get("AIOS_BENCH_AGENTZERO_PROJECT")
        if project:
            environment["AIOS_BENCH_AGENTZERO_PROJECT"] = project
        if model and model != "unknown":
            environment["AIOS_BENCH_REQUESTED_MODEL"] = model
        requested = _requested_model(model)
        return AgentInvocation(
            command,
            environment,
            requested_model=requested,
            # The HTTP service owns the actual model configuration.
            resolved_model=None,
            endpoint=environment["AIOS_BENCH_AGENTZERO_URL"],
            configuration={"project": project, "api_key_configured": bool(environment["AIOS_BENCH_AGENTZERO_API_KEY"])},
        )


class GenericAdapter(Adapter):
    def __init__(self, name: str, executable: str):
        self.name = name
        self.executable = executable

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        template = os.environ.get(f"AIOS_BENCH_{self.name.upper()}_COMMAND")
        if not template:
            command = [self.executable, prompt]
        else:
            command = shlex.split(template) + [prompt]
        requested = _requested_model(model)
        return AgentInvocation(
            command,
            {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())},
            requested_model=requested,
            resolved_model=None,
            configuration={"command_template_configured": bool(template)},
        )


ADAPTERS: dict[str, Adapter] = {
    "hermes": HermesAdapter(),
    "piagent": PiAgentAdapter(),
    "opencode": OpenCodeAdapter(),
    "goose": GooseAdapter(),
    "letta": LettaAdapter(),
    "agentzero": AgentZeroAdapter(),
}
