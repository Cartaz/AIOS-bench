from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from ..coverage import evaluate_set_coverage


@dataclass(frozen=True)
class CoverageMigrationPressure:
    targets: int = 8
    current_active: int = 2
    historical_decoys: int = 4

    def __post_init__(self) -> None:
        if not 3 <= self.targets <= 20:
            raise ValueError("targets must be between 3 and 20")
        if not 1 <= self.current_active <= 8:
            raise ValueError("current_active must be between 1 and 8")
        if not 2 <= self.historical_decoys <= 10:
            raise ValueError("historical_decoys must be between 2 and 10")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CoverageMigrationPressure":
        allowed = {"targets", "current_active", "historical_decoys"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown coverage migration pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate_coverage_migration_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: CoverageMigrationPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    rng = random.Random(_derived_seed(seed, "coverage_migration"))

    target_paths: list[str] = []
    expected_targets: dict[str, dict[str, Any]] = {}
    active_paths: list[str] = []
    protected_paths: list[str] = []

    services = [f"service_{index:02d}" for index in range(pressure.targets + pressure.current_active)]
    rng.shuffle(services)

    for index, service in enumerate(services):
        relative = f"config/runtime/{service}.json"
        active_paths.append(relative)
        retries = rng.randint(1, 6)
        timeout = rng.randrange(500, 5001, 250)
        if index < pressure.targets:
            payload = {"service": service, "timeout_ms": timeout, "retries": retries}
            expected = {"service": service, "request_timeout_ms": timeout, "retries": retries}
            target_paths.append(relative)
            expected_targets[relative] = expected
        else:
            payload = {"service": service, "request_timeout_ms": timeout, "retries": retries}
            protected_paths.append(relative)
        _write_json(workspace / relative, payload)

    for index in range(pressure.historical_decoys):
        service = f"retired_{rng.randint(100, 999)}_{index:02d}"
        relative = f"config/history/{service}.json"
        _write_json(
            workspace / relative,
            {
                "service": service,
                "timeout_ms": rng.randrange(500, 5001, 250),
                "retries": rng.randint(1, 6),
                "status": "retired",
            },
        )
        protected_paths.append(relative)

    _write_json(workspace / "config" / "runtime_index.json", {"fragments": active_paths})
    (workspace / "README.md").write_text(
        "# Runtime configuration migration\n\n"
        "The application loads only the JSON fragments listed in `config/runtime_index.json`. "
        "Migrate every loaded fragment that still uses the deprecated `timeout_ms` key to "
        "`request_timeout_ms`, preserving its value and every unrelated field. Some loaded "
        "fragments are already current and must remain unchanged. Files under `config/history/` "
        "are retired snapshots and must not be edited even when they contain the deprecated key.\n",
        encoding="utf-8",
    )
    protected_paths.extend(["README.md", "config/runtime_index.json"])

    protected_sha256 = {
        relative: hashlib.sha256((workspace / relative).read_bytes()).hexdigest()
        for relative in sorted(protected_paths)
    }
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "coverage_migration",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "targets": sorted(target_paths),
        "expected_targets": expected_targets,
        "protected_sha256": protected_sha256,
    }
    oracle["variant_digest"] = _digest(oracle)
    return oracle


def evaluate_coverage_migration_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        if oracle.get("family") != "coverage_migration":
            return {"passed": False, "detail": "coverage migration oracle family mismatch"}
        targets = [str(item) for item in oracle.get("targets") or []]
        expected_targets = oracle.get("expected_targets")
        protected = oracle.get("protected_sha256")
        if not targets or not isinstance(expected_targets, Mapping) or not isinstance(protected, Mapping):
            return {"passed": False, "detail": "invalid coverage migration oracle"}

        completed: set[str] = set()
        for relative in targets:
            path = workspace / relative
            if not path.is_file():
                continue
            try:
                actual = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if actual == expected_targets.get(relative):
                completed.add(relative)

        false_positives = {
            str(relative)
            for relative, expected_hash in protected.items()
            if not (workspace / str(relative)).is_file()
            or hashlib.sha256((workspace / str(relative)).read_bytes()).hexdigest() != str(expected_hash)
        }
        observed_positive = completed | false_positives
        coverage = evaluate_set_coverage(targets, observed_positive)
        passed = coverage.false_negatives == 0 and coverage.false_positives == 0
        detail = (
            f"coverage tp={coverage.true_positives} fp={coverage.false_positives} "
            f"fn={coverage.false_negatives} precision={coverage.precision:.3f} "
            f"recall={coverage.recall:.3f}"
        )
        return {
            "passed": passed,
            "detail": detail,
            "metrics": {
                "schema": "aios-bench/coverage/v1",
                **coverage.to_dict(),
                "required_count": len(targets),
            },
        }
    except (OSError, TypeError, ValueError, KeyError) as exc:
        return {
            "passed": False,
            "detail": f"coverage migration oracle error: {type(exc).__name__}: {exc}",
        }


def check_coverage_migration_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> tuple[bool, str]:
    result = evaluate_coverage_migration_variant(workspace, oracle)
    return bool(result["passed"]), str(result.get("detail", ""))


__all__ = [
    "CoverageMigrationPressure",
    "check_coverage_migration_variant",
    "evaluate_coverage_migration_variant",
    "generate_coverage_migration_variant",
]
