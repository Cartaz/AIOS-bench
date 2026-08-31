from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

from .materialization import ParametricTaskMaterializer
from .models import Task
from .parametric import normalize_parameters


AIOS_INDEX_PROFILE_SCHEMA = "aios-bench/aios-index-profile/v1"
AIOS_INDEX_CONTEXT_KIND = "aios_index"
DEFAULT_AIOS_INDEX_PROFILE = "aios_index_v1"


@dataclass(frozen=True)
class IndexEntry:
    task_id: str
    role: str
    family: str | None = None

    def to_dict(self) -> dict[str, str]:
        value = {"task_id": self.task_id, "role": self.role}
        if self.family is not None:
            value["family"] = self.family
        return value


@dataclass(frozen=True)
class AIOSIndexProfile:
    """Stable compact selection over canonical Frontier v4 tasks.

    The profile owns selection and only the pressure coordinates of the
    selected canonical families. It does not clone task definitions or
    introduce a separate scoring system.
    """

    id: str
    entries: tuple[IndexEntry, ...]

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(entry.task_id for entry in self.entries)

    @property
    def pressure_families(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                entry.family
                for entry in self.entries
                if entry.family is not None
            )
        )

    def parameters(self) -> dict[str, dict[str, int]]:
        """Return canonical pressures only for families selected by this profile."""
        normalized = normalize_parameters()
        unknown = set(self.pressure_families) - set(normalized)
        if unknown:
            raise ValueError(
                "AIOS-Index profile references unknown parametric families: "
                + ", ".join(sorted(unknown))
            )
        return {family: normalized[family] for family in self.pressure_families}

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

    @property
    def comparison_id(self) -> str:
        """Immutable run-comparison identity for this exact profile definition."""
        return f"{self.id}@{self.digest}"

    def select_tasks(self, tasks: Iterable[Task]) -> list[Task]:
        catalog = list(tasks)
        by_id = {task.id: task for task in catalog}
        missing = [task_id for task_id in self.task_ids if task_id not in by_id]
        if missing:
            raise ValueError(
                "AIOS-Index profile references missing tasks: " + ", ".join(missing)
            )
        selected = set(self.task_ids)
        entries = {entry.task_id: entry for entry in self.entries}
        for task_id in self.task_ids:
            task = by_id[task_id]
            outside = [dep for dep in task.depends_on if dep not in selected]
            if outside:
                raise ValueError(
                    f"AIOS-Index task {task_id} requires tasks outside the profile: "
                    + ", ".join(outside)
                )
            expected_family = entries[task_id].family
            if expected_family is not None:
                try:
                    actual_family = ParametricTaskMaterializer.family(task)
                except ValueError as exc:
                    raise ValueError(
                        f"AIOS-Index task {task_id} is not a valid parametric task"
                    ) from exc
                if actual_family != expected_family:
                    raise ValueError(
                        f"AIOS-Index task {task_id} family drift: "
                        f"expected {expected_family}, got {actual_family}"
                    )
        # Preserve canonical catalog order so scheduling and presentation remain
        # aligned with the ordinary Frontier v4 suite.
        return [task for task in catalog if task.id in selected]

    def context(self) -> dict[str, Any]:
        return {
            "kind": AIOS_INDEX_CONTEXT_KIND,
            "profile_schema": AIOS_INDEX_PROFILE_SCHEMA,
            # profile_name remains the stable selection id. profile_id is the
            # immutable comparison identity so old/new profile revisions cannot
            # be silently grouped by reporting code that keys only on profile_id.
            "profile_name": self.id,
            "profile_id": self.comparison_id,
            "profile_digest": self.digest,
            "suite": "frontier_v4",
            "task_count": len(self.entries),
            "task_ids": list(self.task_ids),
            "roles": {entry.task_id: entry.role for entry in self.entries},
            "pressure_coordinates": self.parameters(),
            "interpretation": (
                "compact high-signal profile over canonical Frontier v4 tasks; "
                "reported separately from the full-suite leaderboard"
            ),
        }


def _build_default_profile() -> AIOSIndexProfile:
    # Simpler baseline tasks remain in Frontier v4; the index intentionally uses
    # their stronger descendants where the capabilities overlap.
    entries = (
        IndexEntry(
            "support_dependency_001",
            "stateful_multi_source_autonomy",
            "dependency_world",
        ),
        IndexEntry(
            "data_cross_artifact_001",
            "cross_artifact_consistency",
            "cross_artifact",
        ),
        IndexEntry(
            "reasoning_epistemic_001",
            "premise_verification",
            "epistemic_twins",
        ),
        IndexEntry(
            "retrieval_wide_001",
            "exhaustive_retrieval_provenance",
            "wide_retrieval",
        ),
        IndexEntry(
            "software_black_box_001",
            "black_box_reconstruction",
            "black_box_reconstruction",
        ),
        IndexEntry(
            "tool_use_lineage_001",
            "workspace_dependency_reasoning",
            "workspace_lineage",
        ),
        IndexEntry(
            "tool_recovery_001",
            "tool_selection_recovery",
            "tool_recovery",
        ),
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
