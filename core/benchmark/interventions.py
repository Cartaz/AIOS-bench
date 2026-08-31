from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .models import Task


INTERVENTION_SCHEMA = "aios-bench/intervention/v1"
SKILL_MODES = ("no_skill", "curated_skill")


@dataclass(frozen=True)
class SkillPackage:
    """Benchmark-owned procedural guidance used only for controlled ablations."""

    id: str
    task_ids: frozenset[str]
    content: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


_SKILLS = (
    SkillPackage(
        id="workspace-lineage/v1",
        task_ids=frozenset({"tool_use_lineage_001"}),
        content=(
            "MODULE 1 — Resolve authority by references, not filename recency. Start from the "
            "active release pointer and follow every exact node_id@revision dependency. Traverse "
            "all branches, memoize visited nodes, and treat any revision not reached from the active "
            "root as inactive even when its revision number is larger.\n\n"
            "MODULE 2 — Reconcile only active evidence. Merge settings only from sources referenced "
            "by the active DAG, inventory sources referenced exclusively by inactive revisions, and "
            "verify that every required root-to-shared-base path and the consumer path are represented "
            "before writing the final artifact."
        ),
    ),
    SkillPackage(
        id="tool-recovery/v1",
        task_ids=frozenset({"tool_recovery_001"}),
        content=(
            "MODULE 1 — Discover before acting. Read the tool schema, match exact tool names and typed "
            "arguments, and reject similarly named legacy/preview tools unless the task explicitly "
            "requires them. Treat incomplete responses as evidence that a targeted follow-up read is "
            "needed rather than guessing missing fields.\n\n"
            "MODULE 2 — Recover without duplicating side effects. Retry only errors explicitly marked "
            "retryable. For an ambiguous or lost response after a non-idempotent write, repeat the same "
            "operation with the same idempotency key; never mint a new key for the same intended action. "
            "Stop retrying deterministic schema/validation errors and correct the arguments instead.\n\n"
            "MODULE 3 — Verify completion. Confirm every required mutation exactly once, avoid distractor "
            "tools and extra actions, and check the final observable state before reporting success."
        ),
    ),
)


def _catalog_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": package.id,
            "task_ids": sorted(package.task_ids),
            "digest": package.digest,
        }
        for package in _SKILLS
    ]


SKILL_CATALOG_DIGEST = hashlib.sha256(
    json.dumps(
        _catalog_payload(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
).hexdigest()


def skill_for_task(task: Task) -> SkillPackage | None:
    matches = [package for package in _SKILLS if task.id in package.task_ids]
    if len(matches) > 1:
        raise ValueError(f"task {task.id} has multiple curated skills")
    return matches[0] if matches else None


def skill_task_ids() -> frozenset[str]:
    return frozenset(task_id for package in _SKILLS for task_id in package.task_ids)


@dataclass(frozen=True)
class ExecutionCondition:
    """Controlled inference-time intervention carried by a Frontier v4 runner."""

    skill_mode: str = "no_skill"

    def __post_init__(self) -> None:
        if self.skill_mode not in SKILL_MODES:
            raise ValueError(
                f"skill_mode must be one of {', '.join(SKILL_MODES)}"
            )

    def manifest(self) -> dict[str, Any]:
        # The catalog digest is present in both arms. Removing only skill_mode
        # therefore yields a stable matched-ablation profile while still
        # invalidating comparability when curated guidance changes.
        return {
            "schema": INTERVENTION_SCHEMA,
            "skill_mode": self.skill_mode,
            "skill_catalog_digest": SKILL_CATALOG_DIGEST,
        }

    def task_identity(self, task: Task) -> dict[str, Any]:
        package = skill_for_task(task)
        return {
            "skill_mode": self.skill_mode,
            "skill_available": package is not None,
            "skill_applied": self.skill_mode == "curated_skill" and package is not None,
            "skill_id": package.id if package is not None else None,
            "skill_digest": package.digest if package is not None else None,
        }

    def augment_prompt(self, task: Task, prompt: str) -> str:
        package = skill_for_task(task)
        if self.skill_mode != "curated_skill" or package is None:
            return prompt
        return (
            prompt
            + "\n\nCURATED PROCEDURAL SKILL\n"
            + "Use the following general procedure as guidance. It does not contain variant-specific "
            + "answers; derive all concrete values from the workspace and runtime.\n\n"
            + package.content
        )


__all__ = [
    "ExecutionCondition",
    "INTERVENTION_SCHEMA",
    "SKILL_CATALOG_DIGEST",
    "SKILL_MODES",
    "SkillPackage",
    "skill_for_task",
    "skill_task_ids",
]
