from __future__ import annotations

import os
from pathlib import Path

from .adapters import Adapter, AgentInvocation
from .deepseek_runtime import (
    DEEPSEEK_API_KEY_ENV,
    DEEPSEEK_PROVIDER_ID,
    DEEPSEEK_SANDBOX_HOME,
    validate_endpoint,
    write_settings,
)


class DeepSeekHarnessAdapter(Adapter):
    """Run DeepSeek Harness through its built-in one-shot headless profile.

    AIOS-Bench owns the provider/model settings used for each run rather than
    inheriting the user's ambient DSH_HOME. The retained settings source is
    credential-free; the sandbox mounts it into an otherwise ephemeral DSH_HOME.
    """

    name = "deepseek"
    capabilities = frozenset({"headless", "sessions", "terminal", "skills", "delegation"})

    def build(self, prompt: str, workspace: Path, model: str) -> AgentInvocation:
        requested = model.strip()
        if not requested or requested == "unknown":
            raise ValueError("DeepSeek Harness requires an explicit model id")

        endpoint_value = os.environ.get("AIOS_BENCH_ENDPOINT", "")
        endpoint = validate_endpoint(endpoint_value)
        settings = write_settings(workspace, endpoint=endpoint, model=requested)
        api_key = os.environ.get(DEEPSEEK_API_KEY_ENV, "").strip() or "aios-bench-local"

        environment = {
            "DSH_HOME": str(DEEPSEEK_SANDBOX_HOME),
            "DSH_PERMISSION_MODE": "danger-full-access",
            "DSH_TELEMETRY_DISABLED": "1",
            DEEPSEEK_API_KEY_ENV: api_key,
            # Source consumed only by AIOS-Bench's sandbox plan. It is not a
            # DeepSeek Harness setting and never becomes part of DSH_HOME.
            "AIOS_BENCH_DEEPSEEK_SETTINGS_SOURCE": str(settings),
        }
        return AgentInvocation(
            command=["dsh", "--profile", "headless", prompt],
            environment=environment,
            requested_model=requested,
            resolved_model=requested,
            model_resolution="adapter_pinned_ephemeral_settings",
            provider=DEEPSEEK_PROVIDER_ID,
            endpoint=endpoint,
            configuration={
                "profile": "headless",
                "provider": DEEPSEEK_PROVIDER_ID,
                "ambient_dsh_home_inherited": False,
                "ephemeral_dsh_home": True,
                "settings_read_only": True,
                "telemetry_disabled": True,
                "permission_mode": "danger-full-access_inside_aios_sandbox",
                "api_key_configured": bool(os.environ.get(DEEPSEEK_API_KEY_ENV, "").strip()),
                "structured_events_available": False,
            },
        )
