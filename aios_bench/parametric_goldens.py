from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .golden_solutions import materialize_parametric_golden as _legacy_materializer


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


def materialize_parametric_golden(
    family: str,
    workspace: Path,
    oracle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    registry = {
        "config_traversal": _config_traversal_golden,
    }
    materializer = registry.get(family)
    if materializer is not None:
        return materializer(workspace, oracle)
    return _legacy_materializer(family, workspace, oracle)


__all__ = ["materialize_parametric_golden"]
