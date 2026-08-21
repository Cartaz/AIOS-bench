from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from .agentzero_workspace import template_project_digest


UNKNOWN_MODEL_VALUES = frozenset({"", "unknown"})

# These are hard comparability requirements, not a taxonomy of everything a
# task happens to exercise. Only categories which cannot be evaluated fairly
# without a harness-level facility belong here. Other categories use the
# benchmark-owned workspace and deterministic oracle shared by every adapter.
REQUIRED_CAPABILITIES_BY_CATEGORY: dict[str, frozenset[str]] = {
    "browser": frozenset({"browser"}),
    "subagents": frozenset({"structured_subagent_events"}),
}


def _requested_model(model: str) -> str | None:
    return model if model and model not in UNKNOWN_MODEL_VALUES else None


def _public_service_endpoint(endpoint: str) -> str:
    """Record service identity without credentials, query strings, or fragments."""
    value = str(endpoint or "").strip()
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value.split("?", 1)[0].split("#", 1)[0].rsplit("@", 1)[-1]
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = f":{parsed.port}" if parsed.port is not None else ""
    except ValueError:
        port = ""
    return urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path, "", ""))


@dataclass(frozen=True)
class AgentInvocation:
    command: list[str]
    environment: dict[str, str]
    requested_model: str | None = None
    resolved_model: str | None = None
    model_resolution: str | None = None
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
    runner change. Category requirements remain deliberately conservative so
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
    capabilities = frozenset({
        "skills",
        "delegation",
        "terminal",
        "browser",
        "sessions",
        "token_stats",
    })

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        usage_path = workspace.resolve() / ".aios_bench_hermes_usage.json"
        toolsets = "terminal,file,web,browser,skills,todo,code_execution,delegation"
        command = [
            "hermes", "--ignore-rules", "--toolsets", toolsets,
            "--usage-file", str(usage_path),
        ]
        provider = os.environ.get("AIOS_BENCH_HERMES_PROVIDER")
        if provider:
            command += ["--provider", provider]
        if model and model != "unknown":
            command += ["--model", model]
        command += ["--oneshot", prompt]
        requested = _requested_model(model)
        return AgentInvocation(
            command,
            {
                "AIOS_BENCH_WORKSPACE": str(workspace.resolve()),
                "AIOS_BENCH_HERMES_USAGE_FILE": str(usage_path),
            },
            requested_model=requested,
            resolved_model=requested,
            provider=provider,
            configuration={
                "mode": "oneshot",
                "ignore_rules": True,
                "toolsets": toolsets.split(","),
                "native_memory_tool": False,
                "session_search_tool": False,
                "usage_file": "ephemeral_workspace_sidecar",
                "structured_subagent_events": False,
            },
        )


class PiAgentAdapter(Adapter):
    name = "piagent"
    capabilities = frozenset({"json_events", "rpc", "sessions", "extensions", "tool_events", "token_stats"})

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
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
        "json_events", "sessions", "server", "mcp", "token_stats",
        "tool_events", "structured_subagent_events",
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
    capabilities = frozenset({
        "recipes", "extensions", "sessions", "provider_model", "json_events",
        "tool_events", "terminal", "structured_subagent_events",
    })

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = [
            "goose", "run", "--no-session", "--quiet",
            "--output-format", "stream-json", "--with-builtin", "developer",
        ]
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
            configuration={
                "session": "disabled",
                "quiet": True,
                "output_format": "stream-json",
                "builtin_extensions": ["developer"],
                "summon_delegate": "default_enabled_platform_extension",
            },
        )


class LettaAdapter(Adapter):
    name = "letta"
    capabilities = frozenset({
        "headless", "sessions", "ephemeral", "skills", "json_events",
        "tool_events", "token_stats", "terminal", "structured_subagent_events",
    })

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = [
            "letta", "-p", "--ephemeral", "--output-format", "stream-json",
            "--yolo", "--no-mods", "--skill-sources", "bundled",
        ]
        if model and model != "unknown":
            command += ["--model", model]
        command.append(prompt)
        requested = _requested_model(model)
        return AgentInvocation(
            command,
            {"AIOS_BENCH_WORKSPACE": str(workspace.resolve())},
            requested_model=requested,
            resolved_model=requested,
            configuration={
                "headless": True,
                "ephemeral": True,
                "output_format": "stream-json",
                "permission_mode": "unrestricted",
                "mods": "disabled",
                "skill_sources": ["bundled"],
                "structured_agent_tool": True,
            },
        )


class AgentZeroAdapter(Adapter):
    name = "agentzero"
    capabilities = frozenset({
        "api", "json_events", "tool_events", "structured_subagent_events",
        "browser", "terminal", "projects", "sessions",
    })

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        command = ["python", "-m", "aios_bench.agentzero_client", prompt]
        service_url = os.environ.get("AIOS_BENCH_AGENTZERO_URL", "http://127.0.0.1:80")
        template = os.environ.get("AIOS_BENCH_AGENTZERO_PROJECT", "").strip()
        projects_root = os.environ.get("AIOS_BENCH_AGENTZERO_PROJECTS_ROOT", "").strip()
        profile = os.environ.get("AIOS_BENCH_AGENTZERO_PROFILE", "").strip()
        declared_model = os.environ.get("AIOS_BENCH_AGENTZERO_RESOLVED_MODEL", "").strip()
        provider = os.environ.get("AIOS_BENCH_AGENTZERO_PROVIDER", "").strip() or None
        model_endpoint = os.environ.get("AIOS_BENCH_AGENTZERO_MODEL_ENDPOINT", "").strip() or None
        isolated_service = os.environ.get("AIOS_BENCH_AGENTZERO_ISOLATED_SERVICE", "").strip()
        template_digest = template_project_digest(projects_root or None, template or None)

        environment = {
            "AIOS_BENCH_WORKSPACE": str(workspace.resolve()),
            "AIOS_BENCH_AGENTZERO_URL": service_url,
            "AIOS_BENCH_AGENTZERO_API_KEY": os.environ.get("AIOS_BENCH_AGENTZERO_API_KEY", ""),
            "AIOS_BENCH_AGENTZERO_PROJECT": template,
            "AIOS_BENCH_AGENTZERO_PROJECTS_ROOT": projects_root,
            "AIOS_BENCH_AGENTZERO_PROFILE": profile,
            "AIOS_BENCH_AGENTZERO_RESOLVED_MODEL": declared_model,
            "AIOS_BENCH_AGENTZERO_ISOLATED_SERVICE": isolated_service,
        }
        if model and model != "unknown":
            environment["AIOS_BENCH_REQUESTED_MODEL"] = model

        requested = _requested_model(model)
        resolved = declared_model or None
        if requested and resolved != requested:
            resolved = None

        return AgentInvocation(
            command,
            environment,
            requested_model=requested,
            resolved_model=resolved,
            model_resolution="operator_declared_remote" if resolved else None,
            provider=provider,
            endpoint=model_endpoint,
            configuration={
                "transport": "external_api",
                "service_endpoint": _public_service_endpoint(service_url),
                "project_template": template or None,
                "project_template_digest": template_digest,
                "projects_root_configured": bool(projects_root),
                "agent_profile": profile or None,
                "api_key_configured": bool(environment["AIOS_BENCH_AGENTZERO_API_KEY"]),
                "fresh_context_per_task": True,
                "ephemeral_physical_project_per_task": True,
                "timeout_orphan_isolated_by_project": True,
                "workspace_bridge": "shared_projects_root",
                "context_cleanup": "api_terminate_chat",
                "telemetry": "api_log_get",
                "structured_subagent_log_type": True,
                "native_memory_scope": "ephemeral_project",
                "isolated_service_attestation": isolated_service.lower() in {"1", "true", "yes", "on"},
                "model_binding": "operator_declared_remote",
            },
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
