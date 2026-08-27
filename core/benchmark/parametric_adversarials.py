from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .parametric.runtime_investigation import runtime_probe_payload
from .parametric.tool_branching import expected_resolution


AdversarialMaterializer = Callable[[Path, Mapping[str, Any]], str]


def _write(workspace: Path, relative: str, content: str) -> None:
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _expense_wrong_malformed_count(workspace: Path, oracle: Mapping[str, Any]) -> str:
    primary = oracle.get("primary")
    if not isinstance(primary, Mapping):
        raise ValueError("invalid expense oracle")
    malformed = int(primary.get("malformed_rows", -1))
    totals = primary.get("monthly_totals")
    if malformed < 0 or not isinstance(totals, Mapping):
        raise ValueError("invalid expense oracle")

    tool = '''from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    totals: dict[str, Decimal] = defaultdict(Decimal)
    malformed = 0
    with Path(args.input).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                amount = Decimal(row["amount"])
                month = row["date"][:7]
                if len(month) != 7:
                    raise ValueError("invalid month")
            except (InvalidOperation, KeyError, TypeError, ValueError):
                malformed += 1
                continue
            totals[month] += amount

    lines = ["# Monthly expense report", ""]
    for month in sorted(totals):
        lines.append(f"{month}: {totals[month]:.2f}")
    lines.extend(["", f"Skipped {malformed + 1} malformed rows", ""])
    Path(args.output).write_text("\\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
'''
    _write(workspace, "tools/expense_report.py", tool)
    lines = ["# Monthly expense report", ""]
    for month, total in totals.items():
        lines.append(f"{month}: {total}")
    lines.extend(["", f"Skipped {malformed + 1} malformed rows", ""])
    _write(workspace, "reports/monthly_expense_report.md", "\n".join(lines))
    return "correct_totals_wrong_malformed_count"


def _config_incomplete_chain(workspace: Path, oracle: Mapping[str, Any]) -> str:
    settings = oracle.get("settings")
    chain = oracle.get("reference_chain")
    consumer = str(oracle.get("consumer_path", ""))
    if not isinstance(settings, Mapping) or not isinstance(chain, list) or len(chain) < 2:
        raise ValueError("invalid config traversal oracle")
    lines = ["# Effective configuration", ""]
    for key, value in settings.items():
        lines.append(f"{key}: {value}")
    lines.extend([
        "",
        "reference chain: " + " -> ".join(str(item) for item in chain[:-1]),
        f"consumer: {consumer}",
        "",
    ])
    _write(workspace, "reports/effective_config.md", "\n".join(lines))
    return "correct_settings_incomplete_reference_chain"


def _causal_symptom_only_runtime_patch(workspace: Path, oracle: Mapping[str, Any]) -> str:
    runtime_path = workspace / str(oracle.get("runtime_path", ""))
    backend_port = oracle.get("backend_port")
    if not runtime_path.is_file() or backend_port is None:
        raise ValueError("invalid causal gateway oracle")
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["backend_port"] = int(backend_port)
    runtime_path.write_text(json.dumps(runtime, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return "symptom_only_runtime_patch"


def _runtime_repair_stale_lane(workspace: Path, oracle: Mapping[str, Any]) -> str:
    config_path = workspace / str(oracle.get("config_path", ""))
    stale_lane = str(oracle.get("stale_lane", ""))
    backend_port = oracle.get("backend_port")
    if not config_path.is_file() or not stale_lane or backend_port is None:
        raise ValueError("invalid runtime investigation oracle")
    routes = json.loads(config_path.read_text(encoding="utf-8"))
    routes[stale_lane] = int(backend_port)
    config_path.write_text(json.dumps(routes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path = workspace / str(oracle.get("probe_report_path", "reports/runtime_probe.json"))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(runtime_probe_payload(oracle), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return "probe_observed_but_stale_lane_repaired"


def _tool_branching_fabricated_receipt(workspace: Path, oracle: Mapping[str, Any]) -> str:
    resolution = expected_resolution(oracle)
    resolution["lookup_receipt"] = "fabricated-receipt"
    _write(
        workspace,
        "reports/case_resolution.json",
        json.dumps(resolution, indent=2, sort_keys=True) + "\n",
    )
    return "correct_case_fields_fabricated_lookup_receipt"


def _coverage_partial_migration(workspace: Path, oracle: Mapping[str, Any]) -> str:
    expected = oracle.get("expected_targets")
    if not isinstance(expected, Mapping) or len(expected) < 2:
        raise ValueError("coverage adversarial witness requires at least two targets")
    relative = sorted(str(item) for item in expected)[0]
    payload = expected[relative]
    if not isinstance(payload, Mapping):
        raise ValueError("invalid coverage migration oracle")
    (workspace / relative).write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return "partial_target_set_migration"


def _pristine_partial_refactor(workspace: Path, oracle: Mapping[str, Any]) -> str:
    golden = oracle.get("golden_files")
    if not isinstance(golden, Mapping) or len(golden) < 2:
        raise ValueError("pristine adversarial witness requires at least two golden files")
    relatives = sorted(str(item) for item in golden)
    for relative in relatives[:-1]:
        (workspace / relative).write_text(str(golden[relative]), encoding="utf-8")
    return "all_but_one_required_policy_module"


def _greenfield_memory_only_registry(workspace: Path, oracle: Mapping[str, Any]) -> str:
    max_name_length = int(oracle.get("max_name_length", 0))
    if max_name_length < 1:
        raise ValueError("invalid greenfield registry oracle")
    _write(workspace, "submission/registry_app/__init__.py", "from .registry import Registry\n")
    _write(
        workspace,
        "submission/registry_app/registry.py",
        f'''from __future__ import annotations

MAX_NAME_LENGTH = {max_name_length}


class Registry:
    def __init__(self, storage_path) -> None:
        self._entries = {{}}

    def _name(self, value) -> str:
        if not isinstance(value, str):
            raise ValueError("name must be a string")
        name = value.strip().casefold()
        if not name or len(name) > MAX_NAME_LENGTH:
            raise ValueError("invalid name")
        return name

    def add(self, name, value):
        key = self._name(name)
        if key in self._entries or not isinstance(value, str) or not value.strip():
            raise ValueError("invalid entry")
        stored = value.strip()
        self._entries[key] = stored
        return {{"name": key, "value": stored}}

    def get(self, name):
        key = self._name(name)
        value = self._entries.get(key)
        return None if value is None else {{"name": key, "value": value}}

    def list_entries(self):
        return [{{"name": key, "value": self._entries[key]}} for key in sorted(self._entries)]

    def remove(self, name):
        key = self._name(name)
        if key not in self._entries:
            return False
        del self._entries[key]
        return True
''',
    )
    return "api_complete_but_nonpersistent_registry"


def materialize_parametric_adversarial(
    family: str,
    workspace: Path,
    oracle: Mapping[str, Any],
) -> str:
    """Apply one deterministic plausible-but-wrong witness for a parametric family."""
    registry: dict[str, AdversarialMaterializer] = {
        "expense_report": _expense_wrong_malformed_count,
        "config_traversal": _config_incomplete_chain,
        "causal_gateway": _causal_symptom_only_runtime_patch,
        "runtime_investigation": _runtime_repair_stale_lane,
        "tool_branching": _tool_branching_fabricated_receipt,
        "coverage_migration": _coverage_partial_migration,
        "pristine_refactor": _pristine_partial_refactor,
        "greenfield_registry": _greenfield_memory_only_registry,
    }
    materializer = registry.get(family)
    if materializer is None:
        raise ValueError(f"no adversarial witness for parametric family {family!r}")
    return materializer(workspace, oracle)


__all__ = ["materialize_parametric_adversarial"]
