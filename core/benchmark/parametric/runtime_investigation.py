from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class RuntimeInvestigationPressure:
    """Workload coordinates for runtime-only state discovery and belief revision."""

    lanes: int = 4
    distractor_docs: int = 2

    def __post_init__(self) -> None:
        if not 3 <= self.lanes <= 8:
            raise ValueError("lanes must be between 3 and 8")
        if not 1 <= self.distractor_docs <= 6:
            raise ValueError("distractor_docs must be between 1 and 6")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeInvestigationPressure":
        allowed = {"lanes", "distractor_docs"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown runtime investigation pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_runtime_investigation_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: RuntimeInvestigationPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    rng = random.Random(_derived_seed(seed, "runtime_investigation"))

    lane_names = ["blue", "green", "canary", "shadow", "amber", "violet", "silver", "gold"][: pressure.lanes]
    active_lane = rng.choice(lane_names)
    stale_lane = rng.choice([lane for lane in lane_names if lane != active_lane])
    backend_port = rng.randint(14000, 22000)

    routes: dict[str, int] = {}
    for lane in lane_names:
        candidate = backend_port
        while candidate == backend_port:
            candidate = rng.randint(22001, 42000)
        routes[lane] = candidate

    config_path = workspace / "config" / "routes.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(routes, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    docs = workspace / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "deployment.md").write_text(
        "# Deployment notes\n\n"
        f"Last recorded active lane: `{stale_lane}`.\n"
        "This document is historical and may lag runtime orchestration state.\n",
        encoding="utf-8",
    )
    distractors: list[str] = []
    for index in range(pressure.distractor_docs):
        path = docs / f"incident_{index + 1:02d}.md"
        path.write_text(
            f"# Historical incident {index + 1}\n\n"
            f"An earlier deployment issue affected `{stale_lane}` and was resolved.\n",
            encoding="utf-8",
        )
        distractors.append(path.relative_to(workspace).as_posix())

    runtime_dir = workspace / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "README.md").write_text(
        "# Runtime probe\n\n"
        "The benchmark starts a local read-only probe for the live orchestration state. "
        "Its endpoint is written to `runtime/endpoint.json` when the task starts. Query `/state` "
        "and save the returned JSON verbatim to `reports/runtime_probe.json` before repairing the active route.\n",
        encoding="utf-8",
    )

    protected = ["docs/deployment.md", "runtime/README.md", *distractors]
    observation_id = hashlib.sha256(f"runtime-observation:{seed}".encode("utf-8")).hexdigest()[:24]
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "runtime_investigation",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "lanes": lane_names,
        "active_lane": active_lane,
        "stale_lane": stale_lane,
        "backend_port": backend_port,
        "initial_routes": routes,
        "observation_id": observation_id,
        "config_path": config_path.relative_to(workspace).as_posix(),
        "probe_report_path": "reports/runtime_probe.json",
        "protected_sha256": {relative: _sha256(workspace / relative) for relative in sorted(protected)},
    }
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def runtime_probe_payload(oracle: Mapping[str, Any]) -> dict[str, Any]:
    active_lane = str(oracle["active_lane"])
    routes = oracle.get("initial_routes")
    if not isinstance(routes, Mapping):
        raise ValueError("runtime investigation oracle is missing initial routes")
    return {
        "observation_id": str(oracle["observation_id"]),
        "active_lane": active_lane,
        "configured_backend_port": int(routes[active_lane]),
        "expected_backend_port": int(oracle["backend_port"]),
        "status": "502",
    }


def check_runtime_investigation_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> tuple[bool, str]:
    try:
        if oracle.get("family") != "runtime_investigation":
            return False, "runtime investigation oracle family mismatch"
        protected = oracle.get("protected_sha256")
        if not isinstance(protected, Mapping):
            return False, "missing protected source digests"
        for relative, expected in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or _sha256(path) != str(expected):
                return False, f"protected runtime-investigation state modified: {relative}"

        routes_path = workspace / str(oracle["config_path"])
        routes = json.loads(routes_path.read_text(encoding="utf-8"))
        initial = oracle.get("initial_routes")
        if not isinstance(routes, Mapping) or not isinstance(initial, Mapping):
            return False, "runtime route map is invalid"

        active_lane = str(oracle["active_lane"])
        expected_port = int(oracle["backend_port"])
        if int(routes.get(active_lane, -1)) != expected_port:
            return False, "live active lane still targets the wrong backend"
        for lane, original_port in initial.items():
            if str(lane) == active_lane:
                continue
            if int(routes.get(str(lane), -1)) != int(original_port):
                return False, f"inactive lane was modified: {lane}"

        report_path = workspace / str(oracle["probe_report_path"])
        if not report_path.is_file():
            return False, "runtime probe evidence missing"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        expected_probe = runtime_probe_payload(oracle)
        if report != expected_probe:
            return False, "runtime probe evidence does not match live benchmark state"
        if active_lane == str(oracle["stale_lane"]):
            return False, "invalid benchmark variant: stale documentation matches live state"
        return True, "runtime evidence contradicted stale documentation and active route was repaired"
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return False, f"runtime investigation parametric oracle error: {type(exc).__name__}: {exc}"
