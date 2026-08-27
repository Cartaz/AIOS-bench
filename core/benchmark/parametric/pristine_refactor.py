from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..pristine import PristineArtifactError, pristine_overlay
from ..pristine_verifier import run_pristine_verifier


@dataclass(frozen=True)
class PristineRefactorPressure:
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PristineRefactorPressure":
        if value:
            raise ValueError(f"pristine refactor has no pressure coordinates: {sorted(value)}")
        return cls()

    def to_dict(self) -> dict[str, int]:
        return {}


def _digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _variant_coordinates(seed: int) -> tuple[int, int, str, str]:
    """Map adjacent seeds to different semantic specs without RNG collisions."""
    express_values = [8, 10, 12, 15, 18]
    priority_values = [25, 30, 35, 40, 45]
    queue_values = ["priority", "rush", "expedite"]
    code_values = ["PRI", "P1", "HOT"]
    coordinate = int(seed) % (
        len(express_values) * len(priority_values) * len(queue_values) * len(code_values)
    )
    express = express_values[coordinate % len(express_values)]
    coordinate //= len(express_values)
    priority = priority_values[coordinate % len(priority_values)]
    coordinate //= len(priority_values)
    queue = queue_values[coordinate % len(queue_values)]
    coordinate //= len(queue_values)
    code = code_values[coordinate % len(code_values)]
    return express, priority, queue, code


def _pricing(express: int, priority: int | None = None) -> str:
    mapping = f'{{"standard": 0, "express": {express}'
    if priority is not None:
        mapping += f', "priority": {priority}'
    mapping += "}"
    return (
        f"SURCHARGES = {mapping}\n\n"
        "def surcharge_for(tier: str) -> int:\n"
        "    try:\n"
        "        return SURCHARGES[tier]\n"
        "    except KeyError as exc:\n"
        "        raise ValueError(f\"unsupported tier: {tier}\") from exc\n"
    )


def _models(include_priority: bool) -> str:
    values = '{"standard", "express"' + (', "priority"' if include_priority else "") + "}"
    return (
        f"ALLOWED_TIERS = {values}\n\n"
        "def validate_tier(tier: str) -> str:\n"
        "    if tier not in ALLOWED_TIERS:\n"
        "        raise ValueError(f\"unsupported tier: {tier}\")\n"
        "    return tier\n"
    )


def _routing(priority_queue: str | None = None) -> str:
    mapping = '{"standard": "normal", "express": "fast"'
    if priority_queue is not None:
        mapping += f', "priority": {priority_queue!r}'
    mapping += "}"
    return (
        f"QUEUES = {mapping}\n\n"
        "def queue_for(tier: str) -> str:\n"
        "    try:\n"
        "        return QUEUES[tier]\n"
        "    except KeyError as exc:\n"
        "        raise ValueError(f\"unsupported tier: {tier}\") from exc\n"
    )


def _serializer(priority_code: str | None = None) -> str:
    mapping = '{"standard": "STD", "express": "EXP"'
    if priority_code is not None:
        mapping += f', "priority": {priority_code!r}'
    mapping += "}"
    return (
        f"WIRE_CODES = {mapping}\n\n"
        "def wire_code(tier: str) -> str:\n"
        "    try:\n"
        "        return WIRE_CODES[tier]\n"
        "    except KeyError as exc:\n"
        "        raise ValueError(f\"unsupported tier: {tier}\") from exc\n"
    )


def _service() -> str:
    return (
        "from .models import validate_tier\n"
        "from .pricing import surcharge_for\n"
        "from .routing import queue_for\n"
        "from .serializer import wire_code\n\n"
        "def process_order(base_amount: int, tier: str) -> dict[str, object]:\n"
        "    validate_tier(tier)\n"
        "    surcharge = surcharge_for(tier)\n"
        "    return {\n"
        "        \"tier\": tier,\n"
        "        \"total\": base_amount + surcharge,\n"
        "        \"queue\": queue_for(tier),\n"
        "        \"wire_code\": wire_code(tier),\n"
        "    }\n"
    )


def _public_tests(express: int) -> str:
    return (
        "import unittest\n\n"
        "from order_service.service import process_order\n\n"
        "class ExistingTierTests(unittest.TestCase):\n"
        "    def test_standard(self):\n"
        "        self.assertEqual(process_order(100, \"standard\"), {\n"
        "            \"tier\": \"standard\", \"total\": 100, \"queue\": \"normal\", \"wire_code\": \"STD\"\n"
        "        })\n\n"
        "    def test_express(self):\n"
        f"        self.assertEqual(process_order(100, \"express\")[\"total\"], {100 + express})\n\n"
        "if __name__ == \"__main__\":\n"
        "    unittest.main()\n"
    )


def generate_pristine_refactor_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: PristineRefactorPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    express_surcharge, priority_surcharge, priority_queue, priority_code = _variant_coordinates(seed)

    baseline_files = {
        "order_service/__init__.py": "",
        "order_service/models.py": _models(False),
        "order_service/pricing.py": _pricing(express_surcharge),
        "order_service/routing.py": _routing(),
        "order_service/serializer.py": _serializer(),
        "order_service/service.py": _service(),
        "tests/test_public.py": _public_tests(express_surcharge),
        "README.md": (
            "# Priority tier rollout\n\n"
            "Complete the existing `priority` tier rollout across the policy modules. "
            f"Priority must add a surcharge of {priority_surcharge}, route to `{priority_queue}`, "
            f"serialize as `{priority_code}`, and be accepted by tier validation. "
            "Existing standard and express behavior must remain unchanged. The public tests cover "
            "existing behavior only; verification also exercises the integrated priority path. "
            "Do not edit README.md, public tests, or order_service/service.py.\n"
        ),
    }
    for relative, content in baseline_files.items():
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    artifact_paths = [
        "order_service/models.py",
        "order_service/pricing.py",
        "order_service/routing.py",
        "order_service/serializer.py",
    ]
    protected_paths = [
        "README.md",
        "tests/test_public.py",
        "order_service/__init__.py",
        "order_service/service.py",
    ]
    golden_files = {
        "order_service/models.py": _models(True),
        "order_service/pricing.py": _pricing(express_surcharge, priority_surcharge),
        "order_service/routing.py": _routing(priority_queue),
        "order_service/serializer.py": _serializer(priority_code),
    }
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "pristine_refactor",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "express_surcharge": express_surcharge,
        "priority_surcharge": priority_surcharge,
        "priority_queue": priority_queue,
        "priority_code": priority_code,
        "baseline_files": baseline_files,
        "artifact_paths": artifact_paths,
        "golden_files": golden_files,
        "protected_sha256": {
            relative: hashlib.sha256((workspace / relative).read_bytes()).hexdigest()
            for relative in protected_paths
        },
    }
    oracle["variant_digest"] = _digest(oracle)
    return oracle


def _hidden_verifier(oracle: Mapping[str, Any]) -> str:
    express = int(oracle["express_surcharge"])
    priority = int(oracle["priority_surcharge"])
    queue = str(oracle["priority_queue"])
    code = str(oracle["priority_code"])
    return f'''\
from order_service.models import validate_tier\nfrom order_service.pricing import surcharge_for\nfrom order_service.routing import queue_for\nfrom order_service.serializer import wire_code\nfrom order_service.service import process_order\n\nassert validate_tier("priority") == "priority"\nassert surcharge_for("priority") == {priority}\nassert queue_for("priority") == {queue!r}\nassert wire_code("priority") == {code!r}\nassert process_order(100, "priority") == {{\n    "tier": "priority", "total": {100 + priority}, "queue": {queue!r}, "wire_code": {code!r}\n}}\nassert process_order(100, "standard") == {{\n    "tier": "standard", "total": 100, "queue": "normal", "wire_code": "STD"\n}}\nassert process_order(100, "express") == {{\n    "tier": "express", "total": {100 + express}, "queue": "fast", "wire_code": "EXP"\n}}\nfor function in (validate_tier, surcharge_for, queue_for, wire_code):\n    try:\n        function("invalid")\n    except ValueError:\n        pass\n    else:\n        raise AssertionError(f"{{function.__name__}} accepted invalid tier")\nprint("pristine verification passed")\n'''


def evaluate_pristine_refactor_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        if oracle.get("family") != "pristine_refactor":
            return {"passed": False, "detail": "pristine refactor oracle family mismatch"}
        baseline = oracle.get("baseline_files")
        artifact_paths = oracle.get("artifact_paths")
        protected = oracle.get("protected_sha256")
        if not isinstance(baseline, Mapping) or not isinstance(artifact_paths, list) or not isinstance(protected, Mapping):
            return {"passed": False, "detail": "invalid pristine refactor oracle"}

        for relative, expected_hash in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != str(expected_hash):
                return {"passed": False, "detail": f"protected file modified: {relative}"}

        with pristine_overlay(
            workspace,
            {str(key): str(value) for key, value in baseline.items()},
            [str(item) for item in artifact_paths],
        ) as (pristine, changes):
            execution = run_pristine_verifier(pristine, _hidden_verifier(oracle), timeout=8)
        passed = execution.returncode == 0
        detail_text = (execution.stdout + "\n" + execution.stderr).strip()[-2000:]
        return {
            "passed": passed,
            "detail": detail_text or f"pristine verifier exited {execution.returncode}",
            "metrics": {
                "schema": "aios-bench/pristine-verification/v2",
                "changed_artifact_count": len(changes),
                "changed_artifacts": changes,
                "verifier_returncode": execution.returncode,
                "pristine_verification_passed": passed,
                "verifier_isolation_strategy": execution.isolation_strategy,
                "verifier_filesystem_confined": execution.filesystem_confined,
                "verifier_network_confined": execution.network_confined,
            },
        }
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        KeyError,
        PristineArtifactError,
        subprocess.TimeoutExpired,
    ) as exc:
        return {
            "passed": False,
            "detail": f"pristine refactor verifier error: {type(exc).__name__}: {exc}",
        }


def check_pristine_refactor_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> tuple[bool, str]:
    result = evaluate_pristine_refactor_variant(workspace, oracle)
    return bool(result["passed"]), str(result.get("detail", ""))


__all__ = [
    "PristineRefactorPressure",
    "check_pristine_refactor_variant",
    "evaluate_pristine_refactor_variant",
    "generate_pristine_refactor_variant",
]
