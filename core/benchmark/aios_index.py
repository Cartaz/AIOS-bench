from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

from .models import Task
from .parametric import normalize_parameters


AIOS_INDEX_PROFILE_SCHEMA = "aios-bench/aios-index-profile/v1"
AIOS_INDEX_CONTEXT_KIND = "aios_index"
DEFAULT_AIOS_INDEX_PROFILE = "aios_index_v1"


@dataclass(frozen=True)
class IndexEntry:
    task_id: str
    role: str

    def to_dict(self) -> dict[str, str]:
        return {"task_id": self.task_id, "role": self.role}


@dataclass(frozen=True)
class AIOSIndexProfile:
    """Stable compact selection over canonical Frontier v4 tasks.

    The profile owns selection and the effective pressure manifest, but it does
    not clone task definitions or introduce a separate scoring system.
    """

    id: str
    entries: tuple[IndexEntry, ...]

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(entry.task_id for entry in self.entries)

    def parameters(self) -> dict[str, dict[str, int]]:
        """Return the complete canonical pressure manifest used by this profile."""
        return normalize_parameters()

    @property
    def digest(self) -> str:
        payload = {
            "schema": AIOS_INDEX_PROFILE_SCHEMA,
            "id": self.id,
            "suite": "frontier_v4",
            "entries": [entry.to_dict() for entry in self.entries],
            "pressure_coordinates": self.parameters(),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def select_tasks(self, tasks: Iterable[Task]) -> list[Task]:
        catalog = list(tasks)
        by_id = {task.id: task for task in catalog}
        missing = [task_id for task_id in self.task_ids if task_id not in by_id]
        if missing:
            raise ValueError(
                "AIOS-Index profile references missing tasks: " + ", ".join(missing)
            )
        selected = set(self.task_ids)
        for task_id in self.task_ids:
            outside = [dep for dep in by_id[task_id].depends_on if dep not in selected]
            if outside:
                raise ValueError(
                    f"AIOS-Index task {task_id} requires tasks outside the profile: "
                    + ", ".join(outside)
                )
        # Preserve canonical catalog order so scheduling and presentation remain
        # aligned with the ordinary Frontier v4 suite.
        return [task for task in catalog if task.id in selected]

    def context(self) -> dict[str, Any]:
        parameters = self.parameters()
        selected_families = {
            family: parameters[family]
            for family in (
                "dependency_world",
                "workspace_lineage",
                "tool_recovery",
                "wide_retrieval",
                "cross_artifact",
                "epistemic_twins",
                "black_box_reconstruction",
            )
        }
        return {
            "kind": AIOS_INDEX_CONTEXT_KIND,
            "profile_schema": AIOS_INDEX_PROFILE_SCHEMA,
            "profile_id": self.id,
            "profile_digest": self.digest,
            "suite": "frontier_v4",
            "task_count": len(self.entries),
            "task_ids": list(self.task_ids),
            "roles": {entry.task_id: entry.role for entry in self.entries},
            "pressure_coordinates": selected_families,
            "interpretation": (
                "compact high-signal profile over canonical Frontier v4 tasks; "
                "reported separately from the full-suite leaderboard"
            ),
        }


def _build_default_profile() -> AIOSIndexProfile:
    # Simpler baseline tasks remain in Frontier v4; the index intentionally uses
    # their stronger descendants where the capabilities overlap.
    entries = (
        IndexEntry("support_dependency_001", "stateful_multi_source_autonomy"),
        IndexEntry("data_cross_artifact_001", "cross_artifact_consistency"),
        IndexEntry("reasoning_epistemic_001", "premise_verification"),
        IndexEntry("retrieval_wide_001", "exhaustive_retrieval_provenance"),
        IndexEntry("software_black_box_001", "black_box_reconstruction"),
        IndexEntry("tool_use_lineage_001", "workspace_dependency_reasoning"),
        IndexEntry("tool_recovery_001", "tool_selection_recovery"),
    )
    profile = AIOSIndexProfile(DEFAULT_AIOS_INDEX_PROFILE, entries)
    if len(profile.task_ids) != len(set(profile.task_ids)):
        raise ValueError("AIOS-Index task ids must be unique")
    return profile


_DEFAULT_PROFILE = _build_default_profile()
AIOS_INDEX_PROFILES = {DEFAULT_AIOS_INDEX_PROFILE: _DEFAULT_PROFILE}


def get_aios_index_profile(
    profile_id: str = DEFAULT_AIOS_INDEX_PROFILE,
) -> AIOSIndexProfile:
    try:
        return AIOS_INDEX_PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"unknown AIOS-Index profile: {profile_id}") from exc


__all__ = [
    "AIOS_INDEX_CONTEXT_KIND",
    "AIOS_INDEX_PROFILE_SCHEMA",
    "AIOS_INDEX_PROFILES",
    "AIOSIndexProfile",
    "DEFAULT_AIOS_INDEX_PROFILE",
    "IndexEntry",
    "get_aios_index_profile",
]
