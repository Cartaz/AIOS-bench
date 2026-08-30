from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ToolRecoveryPressure:
    """Concrete workload coordinates for typed-tool recovery scenarios."""

    case_count: int = 24
    required_actions: int = 5
    distractor_tools: int = 4
    transient_failures: int = 3
    incomplete_responses: int = 8

    def __post_init__(self) -> None:
        if not 10 <= self.case_count <= 256:
            raise ValueError("case_count must be between 10 and 256")
        if not 1 <= self.required_actions <= min(32, self.case_count // 3):
            raise ValueError(
                "required_actions must be between 1 and min(32, case_count//3)"
            )
        if not 2 <= self.distractor_tools <= 16:
            raise ValueError("distractor_tools must be between 2 and 16")
        if not self.required_actions <= self.incomplete_responses <= self.case_count:
            raise ValueError(
                "incomplete_responses must be between required_actions and case_count"
            )
        if not 1 <= self.transient_failures <= min(
            24,
            self.required_actions + self.incomplete_responses,
        ):
            raise ValueError(
                "transient_failures must be between 1 and min(24, required_actions+incomplete_responses)"
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ToolRecoveryPressure":
        allowed = {
            "case_count",
            "required_actions",
            "distractor_tools",
            "transient_failures",
            "incomplete_responses",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown tool recovery pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _case_id(index: int) -> str:
    return f"CASE-{index:04d}"


def _target_case(
    rng: random.Random,
    *,
    index: int,
    threshold: int,
    active_regions: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "id": _case_id(index),
        "status": "pending",
        "priority": rng.randint(threshold, 5),
        "region": rng.choice(active_regions),
        "processed": False,
        "process_count": 0,
        "subject": f"Generated current case {index}",
    }


def _non_target_case(
    rng: random.Random,
    *,
    index: int,
    threshold: int,
    active_regions: tuple[str, ...],
    inactive_regions: tuple[str, ...],
) -> dict[str, Any]:
    reason = rng.randrange(3)
    if reason == 0:
        status = rng.choice(["closed", "resolved"])
        priority = rng.randint(threshold, 5)
        region = rng.choice(active_regions)
    elif reason == 1:
        status = "pending"
        priority = rng.randint(1, threshold - 1)
        region = rng.choice(active_regions)
    else:
        status = "pending"
        priority = rng.randint(threshold, 5)
        region = rng.choice(inactive_regions)
    return {
        "id": _case_id(index),
        "status": status,
        "priority": priority,
        "region": region,
        "processed": False,
        "process_count": 0,
        "subject": f"Generated current case {index}",
    }


def _distractor_names(count: int) -> list[str]:
    candidates = [
        "cases.list_archive",
        "cases.get_cached",
        "actions.process_preview",
        "actions.process_legacy",
        "cases.list_v0",
        "cases.lookup_history",
        "actions.process_dryrun",
        "actions.replay_legacy",
        "cases.get_snapshot",
        "actions.process_bulk_preview",
        "cases.list_deprecated",
        "actions.process_compat",
        "cases.get_replica",
        "actions.validate_only",
        "cases.search_archive",
        "actions.process_shadow",
    ]
    return candidates[:count]


def generate_tool_recovery_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: ToolRecoveryPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "world").mkdir(parents=True, exist_ok=True)
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    rng = random.Random(_derived_seed(seed, "tool-recovery"))

    regions = ("eu", "us", "apac", "latam")
    active_regions = tuple(sorted(rng.sample(regions, 2)))
    inactive_regions = tuple(region for region in regions if region not in active_regions)
    threshold = rng.choice([3, 4])

    cases: list[dict[str, Any]] = []
    target_ids: list[str] = []
    for index in range(1, pressure.required_actions + 1):
        row = _target_case(
            rng,
            index=index,
            threshold=threshold,
            active_regions=active_regions,
        )
        cases.append(row)
        target_ids.append(str(row["id"]))
    for index in range(pressure.required_actions + 1, pressure.case_count + 1):
        cases.append(
            _non_target_case(
                rng,
                index=index,
                threshold=threshold,
                active_regions=active_regions,
                inactive_regions=inactive_regions,
            )
        )
    rng.shuffle(cases)

    all_ids = [str(row["id"]) for row in cases]
    remaining_ids = [case_id for case_id in all_ids if case_id not in target_ids]
    incomplete_ids = list(target_ids)
    if pressure.incomplete_responses > len(incomplete_ids):
        incomplete_ids.extend(
            rng.sample(
                remaining_ids,
                pressure.incomplete_responses - len(incomplete_ids),
            )
        )
    incomplete_ids = sorted(incomplete_ids)

    # Recovery events are split between ambiguous committed writes and transient
    # reads. Every transient read belongs to the incomplete set, so correct
    # decision-making necessarily encounters the injected failure.
    ambiguous_count = min(
        pressure.required_actions,
        max(1, pressure.transient_failures - pressure.incomplete_responses),
    )
    read_failure_count = pressure.transient_failures - ambiguous_count
    if read_failure_count > pressure.incomplete_responses:
        shift = read_failure_count - pressure.incomplete_responses
        ambiguous_count = min(pressure.required_actions, ambiguous_count + shift)
        read_failure_count = pressure.transient_failures - ambiguous_count
    ambiguous_ids = sorted(rng.sample(target_ids, ambiguous_count))
    read_failure_ids = sorted(rng.sample(incomplete_ids, read_failure_count))

    state = {
        "schema": "aios-bench/tool-recovery-state/v1",
        "cases": cases,
    }
    state_path = workspace / "world" / "tool_recovery_state.json"
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    policy = workspace / "policy" / "current_processing.md"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(
        "# Current case-processing policy\n\n"
        "A case must be processed if and only if all conditions are true:\n\n"
        "1. `status` is exactly `pending`;\n"
        f"2. `priority` is at least {threshold};\n"
        f"3. `region` is one of: {', '.join(active_regions)}.\n\n"
        "Use only tools whose schema lifecycle is `active`. List responses can omit decision "
        "fields; resolve every row marked `complete=false` with the exact current read tool. "
        "Errors declare whether they are retryable. Never blindly retry schema errors. For a "
        "retryable `response_lost` from a write, the mutation may already have committed: replay "
        "the identical action using the same idempotency key.\n",
        encoding="utf-8",
    )

    readme = workspace / "README.md"
    readme.write_text(
        "# Typed tool recovery workflow\n\n"
        "The operational case state is benchmark-owned while the task runs. Interact with it only "
        "through `tools/tool_api.py`. Start with `python tools/tool_api.py schema`, then invoke an "
        "exact tool using `python tools/tool_api.py invoke TOOL --args '{...}'`.\n\n"
        "Read `policy/current_processing.md`, identify every and only matching current case, and "
        "apply the current processing action exactly once per target. Handle declared retryable "
        "failures without duplicating non-idempotent effects. Do not use legacy/compatibility tools.\n\n"
        "After verification create `reports/tool_recovery_summary.json` containing exactly two "
        "semantic arrays: `processed_case_ids` for every processed target and `recovered_case_ids` "
        "for cases whose processing returned `response_lost` and was recovered by replaying the "
        "same idempotency key. IDs may be in any order. Do not modify policy files or generated "
        "source files.\n",
        encoding="utf-8",
    )

    distractor_tools = _distractor_names(pressure.distractor_tools)
    protected = ["README.md", "policy/current_processing.md"]
    baseline_cases = sorted((dict(row) for row in cases), key=lambda row: str(row["id"]))
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "tool_recovery",
        "scenario": "typed_case_processing",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "state_path": "world/tool_recovery_state.json",
        "baseline_cases": baseline_cases,
        "target_ids": sorted(target_ids),
        "incomplete_case_ids": incomplete_ids,
        "transient_read_case_ids": read_failure_ids,
        "ambiguous_write_case_ids": ambiguous_ids,
        "distractor_tool_names": distractor_tools,
        "max_attempts_per_operation": 4,
        "decision_reference": {
            "priority_threshold": threshold,
            "active_regions": list(active_regions),
        },
        "protected_sha256": {
            relative: _sha256(workspace / relative)
            for relative in sorted(protected)
        },
    }
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def check_tool_recovery_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> tuple[bool, str]:
    try:
        if oracle.get("family") != "tool_recovery":
            return False, "tool recovery oracle family mismatch"
        if oracle.get("scenario") != "typed_case_processing":
            return False, "unknown tool recovery scenario"

        protected = oracle.get("protected_sha256")
        if not isinstance(protected, Mapping):
            return False, "missing protected source digests"
        for relative, expected_digest in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or _sha256(path) != str(expected_digest):
                return False, f"protected source modified: {relative}"

        state_path = workspace / str(oracle.get("state_path", ""))
        if not state_path.is_file():
            return False, "tool recovery final state missing"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("schema") != "aios-bench/tool-recovery-state/v1":
            return False, "tool recovery state schema mismatch"
        current_value = state.get("cases")
        baseline_value = oracle.get("baseline_cases")
        if not isinstance(current_value, list) or not isinstance(baseline_value, list):
            return False, "invalid tool recovery state/oracle"
        current = {
            str(row["id"]): dict(row)
            for row in current_value
            if isinstance(row, Mapping) and row.get("id") is not None
        }
        baseline = {
            str(row["id"]): dict(row)
            for row in baseline_value
            if isinstance(row, Mapping) and row.get("id") is not None
        }
        if set(current) != set(baseline):
            return False, "tool recovery case set changed"
        targets = {str(value) for value in oracle.get("target_ids") or []}
        mutable = {"processed", "process_count"}
        for case_id, before in baseline.items():
            after = current[case_id]
            for field, value in before.items():
                if field not in mutable and after.get(field) != value:
                    return False, f"immutable case field modified: {case_id}.{field}"
            if case_id in targets:
                if after.get("processed") is not True or after.get("process_count") != 1:
                    return False, f"target case process state incorrect: {case_id}"
            elif after != before:
                return False, f"non-target case modified: {case_id}"

        report_path = workspace / "reports" / "tool_recovery_summary.json"
        if not report_path.is_file():
            return False, "tool recovery summary missing"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or set(report) != {
            "processed_case_ids",
            "recovered_case_ids",
        }:
            return False, "tool recovery summary schema mismatch"
        processed = report.get("processed_case_ids")
        recovered = report.get("recovered_case_ids")
        if not isinstance(processed, list) or not isinstance(recovered, list):
            return False, "tool recovery summary arrays are invalid"
        if {str(value) for value in processed} != targets:
            return False, "tool recovery processed-case report mismatch"
        expected_recovered = {
            str(value) for value in oracle.get("ambiguous_write_case_ids") or []
        }
        if {str(value) for value in recovered} != expected_recovered:
            return False, "tool recovery recovered-case report mismatch"

        return True, "tool recovery final state and report verified"
    except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        return False, f"tool recovery parametric oracle error: {type(exc).__name__}: {exc}"


__all__ = [
    "ToolRecoveryPressure",
    "check_tool_recovery_variant",
    "generate_tool_recovery_variant",
]
