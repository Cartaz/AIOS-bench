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
        command = ["hermes", "chat", "-q", prompt]
        if model and model != "unknown":
            command[2:2] = ["--model", model]
        env = {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())}
        return AgentInvocation(command, env)


class PiAgentAdapter(Adapter):
    name = "piagent"

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["pi", "-p", prompt]
        if model and model != "unknown":
            command[1:1] = ["--model", model]
        env = {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())}
        return AgentInvocation(command, env)


class OpenCodeAdapter(Adapter):
    name = "opencode"

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["opencode", "run", "--dir", str(workspace.resolve()), "--format", "json"]
        if model and model != "unknown":
            command += ["--model", model]
        command.append(prompt)
        return AgentInvocation(command, {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())})


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
    "goose": GenericAdapter("goose", "goose"),
    "letta": GenericAdapter("letta", "letta"),
    "agentzero": GenericAdapter("agentzero", "agent-zero"),
}
