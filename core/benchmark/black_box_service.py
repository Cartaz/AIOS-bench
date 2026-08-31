from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


INPUT_FIELDS = ("region", "plan", "units", "priority", "active", "tags")
OUTPUT_FIELDS = ("bucket", "score", "normalized_units", "flags")
REGIONS = ("eu", "us", "apac", "latam")
PLANS = ("basic", "plus", "pro")
TAGS = ("alpha", "beta", "gamma", "delta")


class BlackBoxInputError(ValueError):
    pass


def _int(value: object, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BlackBoxInputError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise BlackBoxInputError(f"{name} must be between {minimum} and {maximum}")
    return value


def validate_record(record: Mapping[str, Any], *, max_units: int) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise BlackBoxInputError("input must be a JSON object")
    missing = [field for field in INPUT_FIELDS if field not in record]
    if missing:
        raise BlackBoxInputError(f"missing required fields: {', '.join(missing)}")
    region = record["region"]
    plan = record["plan"]
    if region not in REGIONS:
        raise BlackBoxInputError("region is invalid")
    if plan not in PLANS:
        raise BlackBoxInputError("plan is invalid")
    units = _int(record["units"], "units", 0, max_units)
    priority = _int(record["priority"], "priority", 0, 5)
    active = record["active"]
    if not isinstance(active, bool):
        raise BlackBoxInputError("active must be a boolean")
    tags = record["tags"]
    if not isinstance(tags, list) or any(tag not in TAGS for tag in tags):
        raise BlackBoxInputError("tags must be a JSON array containing known tag strings")
    if len(set(tags)) != len(tags):
        raise BlackBoxInputError("tags must not contain duplicates")
    return {
        "region": str(region),
        "plan": str(plan),
        "units": units,
        "priority": priority,
        "active": active,
        "tags": sorted(str(tag) for tag in tags),
    }


def reference_transform(spec: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one hidden deterministic reference program.

    The composition is intentionally simple enough to reverse engineer through
    differential probes, but its seeded constants and enabled rules remain
    outside the agent workspace.
    """
    max_units = int(spec["max_units"])
    value = validate_record(record, max_units=max_units)
    enabled = set(str(rule) for rule in spec["enabled_rules"])

    units = int(value["units"])
    quantum = int(spec["round_quantum"])
    normalized_units = units
    if "quantize_units" in enabled and units:
        normalized_units = ((units + quantum - 1) // quantum) * quantum

    score = normalized_units
    if "plan_multiplier" in enabled:
        score *= int(spec["plan_multipliers"][value["plan"]])
    if "region_offset" in enabled:
        score += int(spec["region_offsets"][value["region"]])
    if "priority_weight" in enabled:
        score += int(value["priority"]) * int(spec["priority_weight"])
    if "active_adjustment" in enabled:
        score += int(spec["active_bonus"]) if value["active"] else -int(spec["inactive_penalty"])
    if "tag_bonus" in enabled and spec["special_tag"] in value["tags"]:
        score += int(spec["special_tag_bonus"])
    if "bulk_bonus" in enabled and units >= int(spec["bulk_threshold"]):
        score += int(spec["bulk_bonus"])
    if "premium_bonus" in enabled and value["plan"] == spec["premium_plan"]:
        score += int(spec["premium_bonus"])
    score = max(0, int(score))

    low, high = (int(item) for item in spec["bucket_thresholds"])
    if score < low:
        bucket = "low"
    elif score < high:
        bucket = "standard"
    else:
        bucket = "high"

    flags: list[str] = []
    if not value["active"]:
        flags.append("inactive")
    if int(value["priority"]) >= int(spec["priority_flag_threshold"]):
        flags.append("priority")
    if "tag_bonus" in enabled and spec["special_tag"] in value["tags"]:
        flags.append(f"tag:{spec['special_tag']}")
    if "bulk_bonus" in enabled and units >= int(spec["bulk_threshold"]):
        flags.append("bulk")
    if "premium_bonus" in enabled and value["plan"] == spec["premium_plan"]:
        flags.append("premium")

    return {
        "bucket": bucket,
        "score": score,
        "normalized_units": normalized_units,
        "flags": sorted(flags),
    }


def probe_log_path(run_dir: Path, task_id: str) -> Path:
    return Path(run_dir) / "black_box" / f"{task_id}.probes.jsonl"


@dataclass
class BlackBoxReferenceService:
    spec: Mapping[str, Any]
    budget: int
    log_path: Path
    probes_used: int = 0

    def contract(self) -> dict[str, Any]:
        return {
            "schema": "aios-bench/black-box-contract/v1",
            "input": {
                "type": "object",
                "required": list(INPUT_FIELDS),
                "region": list(REGIONS),
                "plan": list(PLANS),
                "units": {"minimum": 0, "maximum": int(self.spec["max_units"])},
                "priority": {"minimum": 0, "maximum": 5},
                "active": "boolean",
                "tags": list(TAGS),
                "unknown_fields": "accepted and ignored",
            },
            "output": {
                "type": "object",
                "exact_fields": list(OUTPUT_FIELDS),
                "bucket": ["low", "standard", "high"],
                "score": "non-negative integer",
                "normalized_units": "non-negative integer",
                "flags": "sorted unique string array",
            },
            "probe_budget": int(self.budget),
            "probes_remaining": max(0, int(self.budget) - int(self.probes_used)),
        }

    def probe(self, record: Mapping[str, Any]) -> dict[str, Any]:
        if self.probes_used >= self.budget:
            raise BlackBoxInputError("probe budget exhausted")
        normalized = validate_record(record, max_units=int(self.spec["max_units"]))
        output = reference_transform(self.spec, normalized)
        self.probes_used += 1
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "index": self.probes_used,
            "input_sha256": hashlib.sha256(
                json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return {
            "output": output,
            "probes_used": self.probes_used,
            "probes_remaining": self.budget - self.probes_used,
        }


__all__ = [
    "BlackBoxInputError",
    "BlackBoxReferenceService",
    "INPUT_FIELDS",
    "OUTPUT_FIELDS",
    "PLANS",
    "REGIONS",
    "TAGS",
    "probe_log_path",
    "reference_transform",
    "validate_record",
]
