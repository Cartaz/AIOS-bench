from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .golden_solutions import materialize_parametric_golden as _legacy_materializer
from .parametric.runtime_investigation import runtime_probe_payload


def _write(workspace: Path, relative: str, content: str) -> None:
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _config_traversal_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    settings = oracle.get("settings") or {}
    chain = oracle.get("reference_chain") or []
    consumer = str(oracle.get("consumer_path", ""))
    if not isinstance(settings, Mapping) or not isinstance(chain, list):
        raise ValueError("invalid config traversal oracle")

    lines = ["# Effective configuration", ""]
    for key, value in settings.items():
        lines.append(f"{key}: {value}")
    lines.extend([
        "",
        "reference chain: " + " -> ".join(str(item) for item in chain),
        f"consumer: {consumer}",
        "",
    ])
    _write(workspace, "reports/effective_config.md", "\n".join(lines))
    return []


def _causal_gateway_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    template_relative = str(oracle.get("template_path", ""))
    backend_port = oracle.get("backend_port")
    if not template_relative or backend_port is None:
        raise ValueError("invalid causal gateway oracle")

    template_path = workspace / template_relative
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template["backend_port"] = int(backend_port)
    template_path.write_text(
        json.dumps(template, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return []


def _runtime_investigation_golden(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    config_path = workspace / str(oracle.get("config_path", ""))
    active_lane = str(oracle.get("active_lane", ""))
    backend_port = oracle.get("backend_port")
    if not config_path.is_file() or not active_lane or backend_port is None:
        raise ValueError("invalid runtime investigation oracle")

    routes = json.loads(config_path.read_text(encoding="utf-8"))
    routes[active_lane] = int(backend_port)
    config_path.write_text(
        json.dumps(routes, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = workspace / str(oracle.get("probe_report_path", "reports/runtime_probe.json"))
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(runtime_probe_payload(oracle), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return []


def materialize_parametric_golden(
    family: str,
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    registry = {
        "config_traversal": _config_traversal_golden,
        "causal_gateway": _causal_gateway_golden,
        "runtime_investigation": _runtime_investigation_golden,
    }
    materializer = registry.get(family)
    if materializer is not None:
        return materializer(workspace, oracle)
    return _legacy_materializer(family, workspace, oracle)


__all__ = ["materialize_parametric_golden"]
