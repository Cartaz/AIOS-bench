from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ..task_runtime import TaskRuntime
from ..world_api import start_support_world_runtime, write_world_api_client
from ..world_service import SupportWorldService, verify_support_action_log
from .config_traversal import (
    ConfigTraversalPressure,
    check_config_traversal_variant,
    generate_config_traversal_variant,
)
from .expense import ExpensePressure, check_expense_variant, generate_expense_variant
from .stateful_world import (
    StatefulWorldPressure,
    check_stateful_world_variant,
    generate_stateful_world_variant,
)


FAMILIES = {"expense_report", "config_traversal", "stateful_world"}


def _reseal_variant(oracle: dict[str, Any]) -> dict[str, Any]:
    core = {key: value for key, value in oracle.items() if key != "variant_digest"}
    payload = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    oracle["variant_digest"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return oracle


def materialize_variant(
    family: str,
    workspace: Path,
    *,
    seed: int,
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if family == "expense_report":
        pressure = ExpensePressure.from_mapping(parameters or {})
        return generate_expense_variant(workspace, seed=int(seed), pressure=pressure)
    if family == "config_traversal":
        pressure = ConfigTraversalPressure.from_mapping(parameters or {})
        return generate_config_traversal_variant(workspace, seed=int(seed), pressure=pressure)
    if family == "stateful_world":
        pressure = StatefulWorldPressure.from_mapping(parameters or {})
        oracle = generate_stateful_world_variant(workspace, seed=int(seed), pressure=pressure)
        write_world_api_client(workspace)
        oracle["mutation_interface"] = SupportWorldService.contract()
        return _reseal_variant(oracle)
    raise ValueError(f"unknown parametric family: {family}")


def start_variant_runtime(
    family: str,
    workspace: Path,
    *,
    run_dir: Path,
    task_id: str,
    oracle: Mapping[str, Any],
) -> TaskRuntime:
    if family == "stateful_world":
        return start_support_world_runtime(workspace, run_dir, task_id, oracle)
    return TaskRuntime()


def check_variant(
    family: str,
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None = None,
    task_id: str | None = None,
) -> tuple[bool, str]:
    if family == "expense_report":
        return check_expense_variant(workspace, oracle)
    if family == "config_traversal":
        return check_config_traversal_variant(workspace, oracle)
    if family == "stateful_world":
        passed, detail = check_stateful_world_variant(workspace, oracle)
        if not passed:
            return passed, detail
        provenance_ok, provenance_detail = verify_support_action_log(
            oracle,
            run_dir=run_dir,
            task_id=task_id,
        )
        if not provenance_ok:
            return False, provenance_detail
        return True, f"{detail}; {provenance_detail}"
    return False, f"unknown parametric family: {family}"


__all__ = [
    "ConfigTraversalPressure",
    "ExpensePressure",
    "StatefulWorldPressure",
    "FAMILIES",
    "check_variant",
    "materialize_variant",
    "start_variant_runtime",
]
