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

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        raise NotImplementedError

    def parse_event(self, line: str) -> dict | None:
        return None


class HermesAdapter(Adapter):
    name = "hermes"

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["hermes", "chat"]
        if model and model != "unknown":
            command += ["--model", model]
        command += ["-q", prompt]
        return AgentInvocation(command, {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())})


class PiAgentAdapter(Adapter):
    name = "piagent"

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        # JSON mode is machine-readable and preferable to scraping TUI output.
        command = ["pi", "--mode", "json"]
        if model and model != "unknown":
            command += ["--model", model]
        command += ["-p", prompt]
        return AgentInvocation(command, {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())})


class OpenCodeAdapter(Adapter):
    name = "opencode"

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["opencode", "run", "--dir", str(workspace.resolve()), "--format", "json", "--auto"]
        if model and model != "unknown":
            command += ["--model", model]
        command.append(prompt)
        return AgentInvocation(command, {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())})


class GooseAdapter(Adapter):
    name = "goose"

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        # Goose's non-interactive run mode is the cleanest deterministic entry point.
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

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        # -p is Letta Code's headless/print path. Keep the agent ID optional so
        # cold runs can create/use the configured default while longitudinal runs
        # can pin AIOS_BENCH_LETTA_AGENT.
        command = ["letta", "-p"]
        agent_id = os.environ.get("AIOS_BENCH_LETTA_AGENT")
        if agent_id:
            command += ["--agent", agent_id]
        environment = {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())}
        return AgentInvocation(command + [prompt], environment)


class AgentZeroAdapter(Adapter):
    name = "agentzero"

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        # Agent Zero is primarily a server/UI application. Its documented external
        # API is invoked through the bundled client module rather than an invented
        # CLI flag. The client requires a local A0 server and API key.
        command = ["python", "-m", "aios_bench.agentzero_client", prompt]
        environment = {
            "AIOS_BENCH_WORKSPACE": str(workspace.resolve()),
            "AIOS_BENCH_AGENTZERO_URL": os.environ.get("AIOS_BENCH_AGENTZERO_URL", "http://127.0.0.1:80"),
            "AIOS_BENCH_AGENTZERO_API_KEY": os.environ.get("AIOS_BENCH_AGENTZERO_API_KEY", ""),
        }
        project = os.environ.get("AIOS_BENCH_AGENTZERO_PROJECT")
        if project:
            environment["AIOS_BENCH_AGENTZERO_PROJECT"] = project
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
