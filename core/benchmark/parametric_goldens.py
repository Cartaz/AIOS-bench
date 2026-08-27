from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .golden_solutions import materialize_parametric_golden as _legacy_materializer
from .parametric.runtime_investigation import runtime_probe_payload
from .parametric.tool_branching import expected_resolution


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
    lines.extend(["", "reference chain: " + " -> ".join(str(item) for item in chain), f"consumer: {consumer}", ""])
    _write(workspace, "reports/effective_config.md", "\n".join(lines))
    return []


def _causal_gateway_golden(workspace: Path, oracle: Mapping[str, Any]) -> list[dict[str, Any]]:
    template_relative = str(oracle.get("template_path", ""))
    backend_port = oracle.get("backend_port")
    if not template_relative or backend_port is None:
        raise ValueError("invalid causal gateway oracle")
    template_path = workspace / template_relative
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template["backend_port"] = int(backend_port)
    template_path.write_text(json.dumps(template, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return []


def _runtime_investigation_golden(workspace: Path, oracle: Mapping[str, Any]) -> list[dict[str, Any]]:
    config_path = workspace / str(oracle.get("config_path", ""))
    active_lane = str(oracle.get("active_lane", ""))
    backend_port = oracle.get("backend_port")
    if not config_path.is_file() or not active_lane or backend_port is None:
        raise ValueError("invalid runtime investigation oracle")
    routes = json.loads(config_path.read_text(encoding="utf-8"))
    routes[active_lane] = int(backend_port)
    config_path.write_text(json.dumps(routes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = workspace / str(oracle.get("probe_report_path", "reports/runtime_probe.json"))
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(runtime_probe_payload(oracle), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return []


def _tool_branching_golden(workspace: Path, oracle: Mapping[str, Any]) -> list[dict[str, Any]]:
    report = workspace / "reports" / "case_resolution.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(expected_resolution(oracle), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return []


def _coverage_migration_golden(workspace: Path, oracle: Mapping[str, Any]) -> list[dict[str, Any]]:
    expected = oracle.get("expected_targets")
    if not isinstance(expected, Mapping):
        raise ValueError("invalid coverage migration oracle")
    for relative, payload in expected.items():
        if not isinstance(payload, Mapping):
            raise ValueError("invalid coverage migration target")
        path = workspace / str(relative)
        path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return []


def _pristine_refactor_golden(workspace: Path, oracle: Mapping[str, Any]) -> list[dict[str, Any]]:
    golden = oracle.get("golden_files")
    if not isinstance(golden, Mapping):
        raise ValueError("invalid pristine refactor oracle")
    for relative, content in golden.items():
        path = workspace / str(relative)
        path.write_text(str(content), encoding="utf-8")
    return []


def _greenfield_registry_golden(workspace: Path, oracle: Mapping[str, Any]) -> list[dict[str, Any]]:
    max_name_length = int(oracle.get("max_name_length", 0))
    if max_name_length < 1:
        raise ValueError("invalid greenfield registry oracle")
    _write(workspace, "submission/registry_app/__init__.py", "from .registry import Registry\n\n__all__ = [\"Registry\"]\n")
    _write(
        workspace,
        "submission/registry_app/registry.py",
        f'''from __future__ import annotations\n\nimport json\nfrom pathlib import Path\n\n\nMAX_NAME_LENGTH = {max_name_length}\n\n\ndef _name(value: object) -> str:\n    if not isinstance(value, str):\n        raise ValueError("name must be a string")\n    normalized = value.strip().casefold()\n    if not normalized or len(normalized) > MAX_NAME_LENGTH:\n        raise ValueError("invalid name")\n    return normalized\n\n\ndef _value(value: object) -> str:\n    if not isinstance(value, str):\n        raise ValueError("value must be a string")\n    normalized = value.strip()\n    if not normalized:\n        raise ValueError("invalid value")\n    return normalized\n\n\nclass Registry:\n    def __init__(self, storage_path: str | Path) -> None:\n        self._path = Path(storage_path)\n        self._entries = self._load()\n\n    def _load(self) -> dict[str, str]:\n        if not self._path.exists():\n            return {{}}\n        try:\n            raw = json.loads(self._path.read_text(encoding="utf-8"))\n        except (OSError, json.JSONDecodeError) as exc:\n            raise ValueError("malformed storage") from exc\n        if not isinstance(raw, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in raw.items()):\n            raise ValueError("malformed storage")\n        return dict(raw)\n\n    def _save(self) -> None:\n        self._path.parent.mkdir(parents=True, exist_ok=True)\n        self._path.write_text(json.dumps(self._entries, sort_keys=True) + "\\n", encoding="utf-8")\n\n    def add(self, name: object, value: object) -> dict[str, str]:\n        key = _name(name)\n        if key in self._entries:\n            raise ValueError("duplicate name")\n        stored = _value(value)\n        self._entries[key] = stored\n        self._save()\n        return {{"name": key, "value": stored}}\n\n    def get(self, name: object) -> dict[str, str] | None:\n        key = _name(name)\n        value = self._entries.get(key)\n        return None if value is None else {{"name": key, "value": value}}\n\n    def list_entries(self) -> list[dict[str, str]]:\n        return [{{"name": key, "value": self._entries[key]}} for key in sorted(self._entries)]\n\n    def remove(self, name: object) -> bool:\n        key = _name(name)\n        if key not in self._entries:\n            return False\n        del self._entries[key]\n        self._save()\n        return True\n''',
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
        "tool_branching": _tool_branching_golden,
        "coverage_migration": _coverage_migration_golden,
        "pristine_refactor": _pristine_refactor_golden,
        "greenfield_registry": _greenfield_registry_golden,
    }
    materializer = registry.get(family)
    if materializer is not None:
        return materializer(workspace, oracle)
    return _legacy_materializer(family, workspace, oracle)


__all__ = ["materialize_parametric_golden"]
