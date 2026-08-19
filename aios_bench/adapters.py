from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentInvocation:
    command: list[str]
    environment: dict[str, str]


class Adapter:
    name: str
    capabilities: frozenset[str] = frozenset()

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        raise NotImplementedError

    def parse_event(self, line: str) -> dict | None:
        return None


class HermesAdapter(Adapter):
    name = "hermes"
    capabilities = frozenset({"memory", "skills", "delegation", "terminal", "browser", "sessions"})

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["hermes", "chat", "--quiet"]
        if model and model != "unknown":
            command += ["--model", model]
        command += ["-q", prompt]
        return AgentInvocation(command, {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())})


class PiAgentAdapter(Adapter):
    name = "piagent"
    capabilities = frozenset({"json_events", "rpc", "sessions", "extensions"})

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["pi", "--mode", "json"]
        if model and model != "unknown":
            command += ["--model", model]
        command += ["-p", prompt]
        return AgentInvocation(command, {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())})


class OpenCodeAdapter(Adapter):
    name = "opencode"
    capabilities = frozenset({"json_events", "sessions", "server", "mcp", "token_stats"})

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["opencode", "run", "--dir", str(workspace.resolve()), "--format", "json", "--auto"]
        if model and model != "unknown":
            command += ["--model", model]
        command.append(prompt)
        return AgentInvocation(command, {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())})


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
        return AgentInvocation(command, {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())})


class LettaAdapter(Adapter):
    name = "letta"
    capabilities = frozenset({"memory", "skills", "subagents", "longitudinal", "headless", "sessions"})

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["letta", "-p"]
        agent_id = os.environ.get("AIOS_BENCH_LETTA_AGENT")
        if agent_id:
            command += ["--agent", agent_id]
        environment = {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())}
        # Letta model selection is normally configured inside the agent/provider
        # rather than as a stable top-level CLI flag. Do not fake a model flag.
        if model and model != "unknown":
            environment["AIOS_BENCH_REQUESTED_MODEL"] = model
        return AgentInvocation(command + [prompt], environment)


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
        return AgentInvocation(command, environment)


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
        return AgentInvocation(command, {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())})


ADAPTERS: dict[str, Adapter] = {
    "hermes": HermesAdapter(),
    "piagent": PiAgentAdapter(),
    "opencode": OpenCodeAdapter(),
    "goose": GooseAdapter(),
    "letta": LettaAdapter(),
    "agentzero": AgentZeroAdapter(),
}
