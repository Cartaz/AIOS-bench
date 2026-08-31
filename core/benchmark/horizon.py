from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .parametric import (
    DependencyWorldPressure,
    StatefulWorldPressure,
    ToolRecoveryPressure,
    WideRetrievalPressure,
    WorkspaceLineagePressure,
    normalize_parameters,
)


HORIZON_PROFILE_SCHEMA = "aios-bench/long-horizon-profile/v1"
HORIZON_CONTEXT_KIND = "long_horizon_pressure"
DEFAULT_HORIZON_PROFILE = "generated_long_horizon_v1"


_PRESSURE_TYPES = {
    "stateful_world": StatefulWorldPressure,
    "dependency_world": DependencyWorldPressure,
    "workspace_lineage": WorkspaceLineagePressure,
    "tool_recovery": ToolRecoveryPressure,
    "wide_retrieval": WideRetrievalPressure,
}

_TASK_FAMILIES = {
    "stateful_support_001": "stateful_world",
    "support_dependency_001": "dependency_world",
    "tool_use_lineage_001": "workspace_lineage",
    "tool_recovery_001": "tool_recovery",
    "retrieval_wide_001": "wide_retrieval",
}

_AXIS_ROLES = {
    "stateful_world": {
        "entity_count": "world_size",
        "required_mutations": "state_transition_count",
        "distractor_policies": "distractor_volume",
        "negative_constraints": "protected_near_miss_count",
    },
    "dependency_world": {
        "entity_count": "world_size",
        "account_count": "dependency_lookup_count",
        "required_mutations": "required_action_count",
        "distractor_policies": "distractor_volume",
        "negative_constraints": "protected_near_miss_count",
    },
    "workspace_lineage": {
        "lineage_depth": "dependency_depth",
        "branch_count": "dependency_branching",
        "stale_revisions": "stale_revision_count",
        "distractor_files": "distractor_volume",
        "extra_settings": "authoritative_payload_width",
    },
    "tool_recovery": {
        "case_count": "world_size",
        "required_actions": "required_action_count",
        "distractor_tools": "distractor_volume",
        "transient_failures": "recovery_event_count",
        "incomplete_responses": "followup_read_count",
    },
    "wide_retrieval": {
        "corpus_size": "corpus_size",
        "target_count": "required_item_count",
        "duplicate_records": "duplicate_distractor_count",
        "conflict_records": "conflicting_source_count",
        "source_depth": "authoritative_source_depth",
    },
}


@dataclass(frozen=True)
class HorizonCell:
    id: str
    index: int
    family: str
    task_id: str
    path_index: int
    parameters: Mapping[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "family": self.family,
            "task_id": self.task_id,
            "path_index": self.path_index,
            "parameters": dict(self.parameters),
            "axis_roles": dict(_AXIS_ROLES[self.family]),
        }


@dataclass(frozen=True)
class HorizonProfile:
    id: str
    cells: tuple[HorizonCell, ...]

    @property
    def digest(self) -> str:
        payload = {
            "schema": HORIZON_PROFILE_SCHEMA,
            "id": self.id,
            "cells": [cell.to_dict() for cell in self.cells],
        }
        return hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

    def family_cells(self, family: str) -> tuple[HorizonCell, ...]:
        return tuple(cell for cell in self.cells if cell.family == family)

    def parameters_for(self, cell: HorizonCell) -> dict[str, dict[str, int]]:
        """Return a complete canonical v4 pressure manifest for one profile cell."""
        parameters = normalize_parameters()
        parameters[cell.family] = dict(cell.parameters)
        return parameters

    def context_for(self, cell: HorizonCell) -> dict[str, Any]:
        family_cells = self.family_cells(cell.family)
        return {
            "kind": HORIZON_CONTEXT_KIND,
            "profile_schema": HORIZON_PROFILE_SCHEMA,
            "profile_id": self.id,
            "profile_digest": self.digest,
            "profile_cell_count": len(self.cells),
            "profile_cell_ids": [item.id for item in self.cells],
            "family": cell.family,
            "task_id": cell.task_id,
            "cell_id": cell.id,
            "cell_index": cell.index,
            "path_index": cell.path_index,
            "family_cell_count": len(family_cells),
            "family_cell_ids": [item.id for item in family_cells],
            "parameters": dict(cell.parameters),
            "axis_roles": dict(_AXIS_ROLES[cell.family]),
            "interpretation": (
                "ordered generated workload path; descriptive response only, "
                "not an assumed monotonic difficulty scale"
            ),
        }


def _cell(
    index: int,
    family: str,
    task_id: str,
    path_index: int,
    **parameters: int,
) -> HorizonCell:
    pressure_type = _PRESSURE_TYPES[family]
    validated = pressure_type.from_mapping(parameters).to_dict()
    if _TASK_FAMILIES.get(task_id) != family:
        raise ValueError(f"task/family mismatch in horizon profile: {task_id} -> {family}")
    return HorizonCell(
        id=f"{family.replace('_', '-')}-p{path_index}",
        index=index,
        family=family,
        task_id=task_id,
        path_index=path_index,
        parameters=validated,
    )


def _build_default_profile() -> HorizonProfile:
    cells = (
        _cell(1, "stateful_world", "stateful_support_001", 1,
              entity_count=16, required_mutations=2, distractor_policies=1, negative_constraints=2),
        _cell(2, "stateful_world", "stateful_support_001", 2,
              entity_count=48, required_mutations=8, distractor_policies=5, negative_constraints=10),
        _cell(3, "stateful_world", "stateful_support_001", 3,
              entity_count=120, required_mutations=20, distractor_policies=12, negative_constraints=24),
        _cell(4, "dependency_world", "support_dependency_001", 1,
              entity_count=18, account_count=6, required_mutations=2,
              distractor_policies=1, negative_constraints=3),
        _cell(5, "dependency_world", "support_dependency_001", 2,
              entity_count=60, account_count=24, required_mutations=8,
              distractor_policies=5, negative_constraints=12),
        _cell(6, "dependency_world", "support_dependency_001", 3,
              entity_count=160, account_count=80, required_mutations=24,
              distractor_policies=12, negative_constraints=32),
        _cell(7, "workspace_lineage", "tool_use_lineage_001", 1,
              lineage_depth=3, branch_count=2, stale_revisions=1,
              distractor_files=2, extra_settings=1),
        _cell(8, "workspace_lineage", "tool_use_lineage_001", 2,
              lineage_depth=5, branch_count=4, stale_revisions=3,
              distractor_files=10, extra_settings=3),
        _cell(9, "workspace_lineage", "tool_use_lineage_001", 3,
              lineage_depth=8, branch_count=6, stale_revisions=6,
              distractor_files=24, extra_settings=6),
        _cell(10, "tool_recovery", "tool_recovery_001", 1,
              case_count=12, required_actions=2, distractor_tools=2,
              transient_failures=2, incomplete_responses=2),
        _cell(11, "tool_recovery", "tool_recovery_001", 2,
              case_count=48, required_actions=8, distractor_tools=6,
              transient_failures=8, incomplete_responses=16),
        _cell(12, "tool_recovery", "tool_recovery_001", 3,
              case_count=120, required_actions=24, distractor_tools=14,
              transient_failures=20, incomplete_responses=48),
        _cell(13, "wide_retrieval", "retrieval_wide_001", 1,
              corpus_size=48, target_count=6, duplicate_records=4,
              conflict_records=4, source_depth=1),
        _cell(14, "wide_retrieval", "retrieval_wide_001", 2,
              corpus_size=192, target_count=24, duplicate_records=32,
              conflict_records=24, source_depth=3),
        _cell(15, "wide_retrieval", "retrieval_wide_001", 3,
              corpus_size=600, target_count=72, duplicate_records=128,
              conflict_records=96, source_depth=6),
    )
    profile = HorizonProfile(DEFAULT_HORIZON_PROFILE, cells)
    _validate_profile(profile)
    return profile


def _validate_profile(profile: HorizonProfile) -> None:
    if not profile.cells:
        raise ValueError("horizon profile must contain cells")
    ids = [cell.id for cell in profile.cells]
    if len(ids) != len(set(ids)):
        raise ValueError("horizon profile cell ids must be unique")
    indices = [cell.index for cell in profile.cells]
    if indices != list(range(1, len(profile.cells) + 1)):
        raise ValueError("horizon profile cell indices must be contiguous")

    for family in _PRESSURE_TYPES:
        cells = profile.family_cells(family)
        if not cells:
            raise ValueError(f"horizon profile is missing family: {family}")
        path_indices = [cell.path_index for cell in cells]
        if path_indices != list(range(1, len(cells) + 1)):
            raise ValueError(f"horizon path indices are not contiguous for {family}")
        previous: Mapping[str, int] | None = None
        for cell in cells:
            if previous is not None:
                shared = sorted(set(previous) & set(cell.parameters))
                nondecreasing = all(cell.parameters[key] >= previous[key] for key in shared)
                increased = any(cell.parameters[key] > previous[key] for key in shared)
                if not nondecreasing or not increased:
                    raise ValueError(
                        f"horizon workload path must increase concrete coordinates for {family}"
                    )
            previous = cell.parameters


_DEFAULT_PROFILE = _build_default_profile()
HORIZON_PROFILES = {DEFAULT_HORIZON_PROFILE: _DEFAULT_PROFILE}


def get_horizon_profile(profile_id: str = DEFAULT_HORIZON_PROFILE) -> HorizonProfile:
    try:
        return HORIZON_PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"unknown long-horizon profile: {profile_id}") from exc


__all__ = [
    "DEFAULT_HORIZON_PROFILE",
    "HORIZON_CONTEXT_KIND",
    "HORIZON_PROFILE_SCHEMA",
    "HORIZON_PROFILES",
    "HorizonCell",
    "HorizonProfile",
    "get_horizon_profile",
]
