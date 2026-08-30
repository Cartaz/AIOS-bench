from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class WorkspaceLineagePressure:
    """Workload coordinates for revision-pinned workspace lineage discovery."""

    lineage_depth: int = 4
    branch_count: int = 3
    stale_revisions: int = 2
    distractor_files: int = 4
    extra_settings: int = 2

    def __post_init__(self) -> None:
        if not 3 <= self.lineage_depth <= 8:
            raise ValueError("lineage_depth must be between 3 and 8")
        if not 2 <= self.branch_count <= 6:
            raise ValueError("branch_count must be between 2 and 6")
        if not 1 <= self.stale_revisions <= 6:
            raise ValueError("stale_revisions must be between 1 and 6")
        if not 0 <= self.distractor_files <= 24:
            raise ValueError("distractor_files must be between 0 and 24")
        if not 0 <= self.extra_settings <= 6:
            raise ValueError("extra_settings must be between 0 and 6")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "WorkspaceLineagePressure":
        allowed = {
            "lineage_depth",
            "branch_count",
            "stale_revisions",
            "distractor_files",
            "extra_settings",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown workspace lineage pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _node_ref(node_id: str, revision: int) -> str:
    return f"{node_id}@{revision}"


def _node_path(node_id: str, revision: int) -> str:
    return f"lineage/nodes/{node_id}.r{revision}.json"


def _source_path(node_id: str, revision: int) -> str:
    return f"config/sources/{node_id}.r{revision}.json"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _base_settings(rng: random.Random) -> dict[str, Any]:
    return {
        "environment": rng.choice(["production", "staging", "canary"]),
        "service_port": rng.randint(4100, 9800),
        "workers": rng.randint(2, 12),
    }


def _branch_setting_factories(rng: random.Random) -> list[tuple[str, Any]]:
    return [
        ("region", lambda: rng.choice(["eu-central", "eu-west", "us-east", "ap-south"])),
        ("request_timeout_ms", lambda: rng.randrange(1000, 9001, 250)),
        ("max_connections", lambda: rng.randrange(50, 501, 25)),
        ("cache_ttl_s", lambda: rng.randrange(30, 601, 30)),
        ("batch_limit", lambda: rng.randrange(8, 129, 8)),
        ("retry_limit", lambda: rng.randint(1, 7)),
    ]


def _extra_setting_factories(rng: random.Random) -> list[tuple[str, Any]]:
    return [
        ("log_level", lambda: rng.choice(["info", "warning", "error"])),
        ("feature_mode", lambda: rng.choice(["stable", "guarded", "progressive"])),
        ("healthcheck_interval_s", lambda: rng.randrange(5, 61, 5)),
        ("queue_limit", lambda: rng.randrange(100, 1001, 50)),
        ("backoff_ms", lambda: rng.randrange(100, 2001, 100)),
        ("telemetry_sample_pct", lambda: rng.randrange(5, 101, 5)),
    ]


def _decoy_value(value: Any, rng: random.Random) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        delta = rng.randint(1, 17)
        return value + delta if rng.choice([True, False]) else max(0, value - delta)
    if isinstance(value, str):
        return f"legacy-{rng.randint(10, 99)}-{value}"
    return f"legacy-{rng.randint(100, 999)}"


def _logical_nodes(pressure: WorkspaceLineagePressure) -> tuple[str, list[list[str]]]:
    shared = "shared-base"
    branches: list[list[str]] = []
    for branch in range(1, pressure.branch_count + 1):
        branch_nodes = [
            f"branch-{branch:02d}-stage-{stage:02d}"
            for stage in range(1, pressure.lineage_depth - 1)
        ]
        branches.append(branch_nodes)
    return shared, branches


def generate_workspace_lineage_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: WorkspaceLineagePressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    rng = random.Random(_derived_seed(seed, "workspace-lineage"))

    release_id = f"release-{rng.randint(100000, 999999)}"
    consumer_path = "services/runtime_loader.py"
    shared_id, branches = _logical_nodes(pressure)
    logical_ids = ["release", *(node for branch in branches for node in branch), shared_id]
    current_revisions = {
        node_id: rng.randint(pressure.stale_revisions + 3, pressure.stale_revisions + 12)
        for node_id in logical_ids
    }

    effective_settings = _base_settings(rng)
    branch_factories = _branch_setting_factories(rng)
    rng.shuffle(branch_factories)
    branch_settings: dict[str, dict[str, Any]] = {}
    for branch, (key, factory) in zip(
        branches, branch_factories[: pressure.branch_count], strict=True
    ):
        branch_settings[branch[-1]] = {key: factory()}
        effective_settings[key] = branch_settings[branch[-1]][key]

    extra_factories = _extra_setting_factories(rng)
    rng.shuffle(extra_factories)
    base_source_settings: dict[str, Any] = dict(effective_settings)
    for key, factory in extra_factories[: pressure.extra_settings]:
        value = factory()
        base_source_settings[key] = value
        effective_settings[key] = value

    # The shared source owns the common settings and optional extras only. Branch
    # leaf sources own one disjoint setting each, so the authoritative union is
    # unambiguous and requires traversing every branch.
    for branch_setting in branch_settings.values():
        for key in branch_setting:
            base_source_settings.pop(key, None)

    lineage_paths: list[list[str]] = []
    current_node_paths: list[str] = []
    current_source_paths: list[str] = []
    stale_source_paths: list[str] = []
    protected: list[str] = []

    def dependencies_for(node_id: str, *, offset: int) -> list[dict[str, Any]]:
        if node_id == "release":
            return [
                {
                    "node_id": branch[0],
                    "revision": current_revisions[branch[0]] - offset,
                }
                for branch in branches
            ]
        for branch in branches:
            if node_id in branch:
                index = branch.index(node_id)
                if index + 1 < len(branch):
                    child = branch[index + 1]
                else:
                    child = shared_id
                return [{"node_id": child, "revision": current_revisions[child] - offset}]
        return []

    for offset in range(0, pressure.stale_revisions + 1):
        current = offset == 0
        for node_id in logical_ids:
            revision = current_revisions[node_id] - offset
            source_relative = _source_path(node_id, revision)
            node_relative = _node_path(node_id, revision)
            if current:
                source_settings = (
                    base_source_settings
                    if node_id == shared_id
                    else branch_settings.get(node_id, {})
                )
            else:
                source_settings = {
                    key: _decoy_value(value, rng)
                    for key, value in (
                        base_source_settings.items()
                        if node_id == shared_id
                        else branch_settings.get(node_id, {}).items()
                    )
                }

            _write_json(
                workspace / source_relative,
                {
                    "source_id": node_id,
                    "revision": revision,
                    "settings": source_settings,
                },
            )
            node_payload: dict[str, Any] = {
                "node_id": node_id,
                "revision": revision,
                "requires": dependencies_for(node_id, offset=offset),
                "source": source_relative,
            }
            if node_id == "release":
                node_payload["release_id"] = (
                    release_id if current else f"historical-{release_id}-{offset}"
                )
                node_payload["consumer"] = consumer_path
            _write_json(workspace / node_relative, node_payload)
            protected.extend([source_relative, node_relative])
            if current:
                current_node_paths.append(node_relative)
                current_source_paths.append(source_relative)
            else:
                stale_source_paths.append(source_relative)

    root_ref = _node_ref("release", current_revisions["release"])
    for branch in branches:
        refs = [root_ref]
        refs.extend(_node_ref(node_id, current_revisions[node_id]) for node_id in branch)
        refs.append(_node_ref(shared_id, current_revisions[shared_id]))
        lineage_paths.append(refs)

    current_release_path = "lineage/current_release.json"
    _write_json(
        workspace / current_release_path,
        {
            "schema": "aios-bench/workspace-lineage/v1",
            "active_release": release_id,
            "root": {
                "node_id": "release",
                "revision": current_revisions["release"],
            },
        },
    )
    protected.append(current_release_path)

    readme = workspace / "README.md"
    readme.write_text(
        "# Workspace lineage task\n\n"
        "The active deployment is revision-pinned. Start with `lineage/current_release.json`, "
        "then follow each node's exact `node_id` + `revision` requirements through "
        "`lineage/nodes/`. Do not substitute a newer-looking or older revision. The active "
        "graph is a DAG: every root-to-shared-base path is authoritative, and only sources "
        "referenced by the pinned graph contribute effective settings. Historical node "
        "revisions and unrelated config files are distractors.\n\n"
        "Create `reports/workspace_lineage.json` with exactly these semantic fields: "
        "`active_release` (string), `root` (`node_id@revision`), `lineage_paths` (array of "
        "root-to-shared-base arrays using `node_id@revision`), `effective_settings` (object), "
        "`consumer_path` (string), and `ignored_stale_sources` (array containing every source "
        "file referenced only by historical revisions). Do not modify any existing file.\n",
        encoding="utf-8",
    )
    protected.append("README.md")

    consumer = workspace / consumer_path
    consumer.parent.mkdir(parents=True, exist_ok=True)
    consumer.write_text(
        "from __future__ import annotations\n\n"
        "import json\n"
        "from pathlib import Path\n\n"
        "CURRENT_RELEASE = Path(__file__).parents[1] / 'lineage' / 'current_release.json'\n\n"
        "def load_current_release() -> dict:\n"
        "    return json.loads(CURRENT_RELEASE.read_text(encoding='utf-8'))\n",
        encoding="utf-8",
    )
    protected.append(consumer_path)

    distractor_paths: list[str] = []
    setting_items = list(effective_settings.items())
    for index in range(pressure.distractor_files):
        key, value = setting_items[index % len(setting_items)]
        relative = f"config/unrelated/legacy_{index + 1:02d}.json"
        _write_json(
            workspace / relative,
            {
                "note": "unrelated legacy configuration",
                "settings": {key: _decoy_value(value, rng)},
            },
        )
        distractor_paths.append(relative)
        protected.append(relative)

    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "workspace_lineage",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "active_release": release_id,
        "root": root_ref,
        "lineage_paths": lineage_paths,
        "effective_settings": effective_settings,
        "consumer_path": consumer_path,
        "current_node_paths": sorted(current_node_paths),
        "current_source_paths": sorted(current_source_paths),
        "stale_source_paths": sorted(stale_source_paths),
        "distractor_paths": sorted(distractor_paths),
        "protected_sha256": {
            relative: _sha256(workspace / relative) for relative in sorted(protected)
        },
    }
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def _normalize_paths(value: Any) -> list[tuple[str, ...]] | None:
    if not isinstance(value, list):
        return None
    normalized: list[tuple[str, ...]] = []
    for path in value:
        if not isinstance(path, list) or not all(isinstance(item, str) for item in path):
            return None
        normalized.append(tuple(path))
    return normalized


def check_workspace_lineage_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> tuple[bool, str]:
    try:
        if oracle.get("family") != "workspace_lineage":
            return False, "workspace lineage oracle family mismatch"
        protected = oracle.get("protected_sha256")
        if not isinstance(protected, Mapping):
            return False, "missing protected source digests"
        for relative, expected in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or _sha256(path) != str(expected):
                return False, f"protected source modified: {relative}"

        report_path = workspace / "reports" / "workspace_lineage.json"
        if not report_path.is_file():
            return False, "workspace lineage report missing"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, Mapping):
            return False, "workspace lineage report must be a JSON object"

        if report.get("active_release") != oracle.get("active_release"):
            return False, "active release is missing or incorrect"
        if report.get("root") != oracle.get("root"):
            return False, "root lineage revision is missing or incorrect"
        if report.get("consumer_path") != oracle.get("consumer_path"):
            return False, "consumer path is missing or incorrect"

        actual_paths = _normalize_paths(report.get("lineage_paths"))
        expected_paths = _normalize_paths(oracle.get("lineage_paths"))
        if actual_paths is None or expected_paths is None:
            return False, "lineage paths must be arrays of node_id@revision strings"
        if len(actual_paths) != len(expected_paths) or sorted(actual_paths) != sorted(expected_paths):
            return False, "authoritative lineage paths are incomplete or incorrect"

        settings = report.get("effective_settings")
        expected_settings = oracle.get("effective_settings")
        if not isinstance(settings, Mapping) or not isinstance(expected_settings, Mapping):
            return False, "effective settings must be a JSON object"
        if dict(settings) != dict(expected_settings):
            return False, "effective settings do not match the authoritative lineage"

        stale = report.get("ignored_stale_sources")
        expected_stale = oracle.get("stale_source_paths")
        if not isinstance(stale, list) or not all(isinstance(item, str) for item in stale):
            return False, "ignored stale sources must be an array of paths"
        if not isinstance(expected_stale, list):
            return False, "invalid workspace lineage oracle"
        if len(stale) != len(expected_stale) or sorted(stale) != sorted(
            str(item) for item in expected_stale
        ):
            return False, "stale lineage source inventory is incomplete or incorrect"

        return True, "workspace lineage DAG, revision pins, settings and source integrity verified"
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
        return False, f"workspace lineage parametric oracle error: {type(exc).__name__}: {exc}"
