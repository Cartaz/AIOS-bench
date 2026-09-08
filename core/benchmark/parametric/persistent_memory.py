from __future__ import annotations

import hashlib
import json
import random
import string
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .grading import VariantGrade


MEMORY_SCHEMA = "aios-bench/persistent-memory/v1"
PHASES = {"capture", "apply", "update"}
LANGUAGES = ("Python", "TypeScript", "Rust", "Go")
TOOLING_STYLES = ("simple", "strict", "minimal", "modular")
VCS_POLICIES = ("no-commit", "feature-branch-only", "commit-after-tests")
DOC_STYLES = ("concise", "examples-first", "reference-first", "minimal")
TEST_POLICIES = ("targeted-first", "full-suite", "smoke-then-full", "changed-area-first")


@dataclass(frozen=True)
class PersistentMemoryPressure:
    """Workload coordinates for durable-memory selection and maintenance."""

    durable_fact_count: int = 6
    transient_fact_count: int = 3
    distractor_fact_count: int = 4
    update_count: int = 2

    def __post_init__(self) -> None:
        if not 5 <= self.durable_fact_count <= 9:
            raise ValueError("durable_fact_count must be between 5 and 9")
        if not 1 <= self.transient_fact_count <= 12:
            raise ValueError("transient_fact_count must be between 1 and 12")
        if not 0 <= self.distractor_fact_count <= 12:
            raise ValueError("distractor_fact_count must be between 0 and 12")
        if not 1 <= self.update_count <= min(3, self.durable_fact_count - 2):
            raise ValueError("update_count must be between 1 and min(3, durable_fact_count-2)")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PersistentMemoryPressure":
        allowed = {
            "durable_fact_count",
            "transient_fact_count",
            "distractor_fact_count",
            "update_count",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown persistent-memory pressure fields: {sorted(unknown)}")
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _token(rng: random.Random, length: int = 10) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(rng.choice(alphabet) for _ in range(length))


def _initial_preferences(seed: int, pressure: PersistentMemoryPressure) -> dict[str, str]:
    rng = random.Random(_derived_seed(seed, "persistent-memory-preferences"))
    primary = rng.choice(LANGUAGES)
    security_choices = [value for value in LANGUAGES if value != primary]
    preferences: dict[str, str] = {
        "primary_language": primary,
        "tooling_style": rng.choice(TOOLING_STYLES),
        "vcs_policy": rng.choice(VCS_POLICIES),
        "preference_token": _token(rng),
        "security_language": rng.choice(security_choices),
    }
    optional = (
        ("documentation_style", DOC_STYLES),
        ("test_policy", TEST_POLICIES),
        ("package_policy", ("stdlib-first", "existing-deps-first", "minimal-deps")),
        ("naming_style", ("descriptive", "compact", "domain-first")),
    )
    for key, choices in optional[: max(0, pressure.durable_fact_count - 5)]:
        preferences[key] = rng.choice(choices)
    return preferences


def _updated_preferences(
    initial: Mapping[str, str],
    seed: int,
    pressure: PersistentMemoryPressure,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    rng = random.Random(_derived_seed(seed, "persistent-memory-updates"))
    pools: dict[str, tuple[str, ...]] = {
        "primary_language": LANGUAGES,
        "tooling_style": TOOLING_STYLES,
        "vcs_policy": VCS_POLICIES,
        "documentation_style": DOC_STYLES,
        "test_policy": TEST_POLICIES,
        "package_policy": ("stdlib-first", "existing-deps-first", "minimal-deps"),
        "naming_style": ("descriptive", "compact", "domain-first"),
    }
    candidates = [key for key in initial if key in pools]
    rng.shuffle(candidates)
    selected = candidates[: pressure.update_count]
    updated = dict(initial)
    history: list[dict[str, str]] = []
    for key in selected:
        previous = updated[key]
        choices = [value for value in pools[key] if value != previous]
        current = rng.choice(choices)
        updated[key] = current
        history.append({"key": key, "previous": previous, "current": current})
    history.sort(key=lambda row: row["key"])
    return updated, history


def _synthetic_previous_memory(seed: int, pressure: PersistentMemoryPressure) -> dict[str, Any]:
    return {
        "schema": MEMORY_SCHEMA,
        "preferences": _initial_preferences(seed, pressure),
        "history": [],
    }


def _load_existing_memory(workspace: Path) -> dict[str, Any] | None:
    path = workspace / ".agent_memory" / "preferences.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    preferences = value.get("preferences")
    history = value.get("history")
    if (
        value.get("schema") != MEMORY_SCHEMA
        or not isinstance(preferences, dict)
        or not all(isinstance(key, str) and isinstance(item, str) for key, item in preferences.items())
        or not isinstance(history, list)
    ):
        return None
    return {
        "schema": MEMORY_SCHEMA,
        "preferences": dict(preferences),
        "history": list(history),
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_memory_schema_document(workspace: Path) -> str:
    relative = "docs/memory_schema.md"
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Durable memory schema\n\n"
        "Persist durable memory in `.agent_memory/preferences.json` as one JSON object with exactly "
        "these top-level fields:\n\n"
        "```json\n"
        "{\n"
        f'  "schema": "{MEMORY_SCHEMA}",\n'
        '  "preferences": {"preference_key": "string value"},\n'
        '  "history": [{"key": "preference_key", "previous": "old", "current": "new"}]\n'
        "}\n"
        "```\n\n"
        "`preferences` contains durable values only. During initial capture, `history` is an empty "
        "array. During updates, preserve existing history and append one row for each durable change. "
        "Do not store transient values or source-format metadata in the durable memory artifact.\n",
        encoding="utf-8",
    )
    return relative


def _protected(workspace: Path, paths: list[str]) -> dict[str, str]:
    return {relative: _sha256(workspace / relative) for relative in sorted(paths)}


def _capture_workspace(
    workspace: Path,
    *,
    seed: int,
    pressure: PersistentMemoryPressure,
    preferences: Mapping[str, str],
) -> tuple[list[str], dict[str, Any]]:
    rng = random.Random(_derived_seed(seed, "persistent-memory-capture"))
    durable_entries = [
        {"key": key, "value": value, "durability": "durable"}
        for key, value in preferences.items()
    ]
    transient_entries = [
        {
            "key": f"session_instruction_{index:02d}",
            "value": f"temporary-{_token(rng, 6)}",
            "durability": "transient",
        }
        for index in range(1, pressure.transient_fact_count + 1)
    ]
    entries = durable_entries + transient_entries
    rng.shuffle(entries)
    _write_json(
        workspace / "notes" / "current_preferences.json",
        {
            "schema": "aios-bench/preference-source/v1",
            "authority": "current",
            "entries": entries,
        },
    )
    distractors = {
        f"stale_pref_{index:02d}": f"archive-{_token(rng, 6)}"
        for index in range(1, pressure.distractor_fact_count + 1)
    }
    _write_json(
        workspace / "notes" / "archive_preferences.json",
        {
            "schema": "aios-bench/preference-source/v1",
            "authority": "historical",
            "preferences": distractors,
        },
    )
    schema_document = _write_memory_schema_document(workspace)
    (workspace / "README.md").write_text(
        "# Durable memory capture\n\n"
        "Read `notes/current_preferences.json`. Persist every entry marked `durable` and no entry "
        "marked `transient` in `.agent_memory/preferences.json` using the canonical schema documented "
        "in `docs/memory_schema.md`. Historical archive values are distractors. Save "
        "`reports/memory_capture.json` listing `stored_keys` and `excluded_transient_keys`. Do not "
        "modify any supplied input file.\n",
        encoding="utf-8",
    )
    transient_keys = sorted(row["key"] for row in transient_entries)
    expected_memory = {
        "schema": MEMORY_SCHEMA,
        "preferences": dict(sorted(preferences.items())),
        "history": [],
    }
    expected_report = {
        "stored_keys": sorted(preferences),
        "excluded_transient_keys": transient_keys,
    }
    return (
        [
            "README.md",
            schema_document,
            "notes/current_preferences.json",
            "notes/archive_preferences.json",
        ],
        {"memory": expected_memory, "report": expected_report, "report_path": "reports/memory_capture.json"},
    )


def _apply_workspace(
    workspace: Path,
    *,
    seed: int,
    pressure: PersistentMemoryPressure,
) -> tuple[list[str], dict[str, Any]]:
    previous = _load_existing_memory(workspace) or _synthetic_previous_memory(seed, pressure)
    preferences = previous["preferences"]
    required_keys = [
        key
        for key in (
            "primary_language",
            "tooling_style",
            "vcs_policy",
            "security_language",
            "preference_token",
        )
        if key in preferences
    ]
    request_id = hashlib.sha256(f"{seed}:memory-apply".encode("utf-8")).hexdigest()[:12]
    _write_json(
        workspace / "requests" / "tool_profile.json",
        {
            "request_id": request_id,
            "instruction": (
                "Build the requested profile from durable memory. The preference values are "
                "intentionally not repeated here."
            ),
            "required_memory_keys": required_keys,
        },
    )
    (workspace / "README.md").write_text(
        "# Durable memory application\n\n"
        "Retrieve the durable preferences persisted by the preceding memory task. The current request "
        "does not repeat their values. Preserve `.agent_memory/preferences.json` unchanged and save "
        "`reports/memory_application.json` with `request_id`, `preference_token`, and `applied`, where "
        "`applied` contains exactly the requested durable keys except `preference_token`. Do not "
        "invent missing preferences and do not modify supplied request files.\n",
        encoding="utf-8",
    )
    applied_keys = [key for key in required_keys if key != "preference_token"]
    expected_report = {
        "request_id": request_id,
        "preference_token": preferences.get("preference_token"),
        "applied": {key: preferences[key] for key in applied_keys},
    }
    return (
        ["README.md", "requests/tool_profile.json"],
        {
            "memory": previous,
            "report": expected_report,
            "report_path": "reports/memory_application.json",
        },
    )


def _update_workspace(
    workspace: Path,
    *,
    seed: int,
    pressure: PersistentMemoryPressure,
) -> tuple[list[str], dict[str, Any]]:
    previous = _load_existing_memory(workspace) or _synthetic_previous_memory(seed, pressure)
    initial = previous["preferences"]
    updated, changes = _updated_preferences(initial, seed, pressure)
    rng = random.Random(_derived_seed(seed, "persistent-memory-update-transients"))
    transient = {
        f"session_only_{index:02d}": f"ignore-{_token(rng, 6)}"
        for index in range(1, pressure.transient_fact_count + 1)
    }
    _write_json(
        workspace / "updates" / "current.json",
        {
            "schema": "aios-bench/memory-update/v1",
            "durable_changes": {row["key"]: row["current"] for row in changes},
            "transient_session_values": transient,
        },
    )
    (workspace / "README.md").write_text(
        "# Durable memory update\n\n"
        "Apply only `durable_changes` from `updates/current.json` to the existing durable memory. "
        "Preserve every unrelated preference, append one history row per durable change with `key`, "
        "`previous`, and `current`, and do not persist any `transient_session_values`. Save "
        "`reports/memory_update.json` with `changed`, `preserved`, and `transient_ignored`. Do not "
        "modify supplied update files.\n",
        encoding="utf-8",
    )
    previous_history = previous.get("history") if isinstance(previous.get("history"), list) else []
    expected_memory = {
        "schema": MEMORY_SCHEMA,
        "preferences": dict(sorted(updated.items())),
        "history": [*previous_history, *changes],
    }
    changed_keys = {row["key"] for row in changes}
    expected_report = {
        "changed": changes,
        "preserved": {key: value for key, value in sorted(initial.items()) if key not in changed_keys},
        "transient_ignored": sorted(transient),
    }
    return (
        ["README.md", "updates/current.json"],
        {"memory": expected_memory, "report": expected_report, "report_path": "reports/memory_update.json"},
    )


def generate_persistent_memory_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: PersistentMemoryPressure,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    phase = str((context or {}).get("phase", "capture"))
    if phase not in PHASES:
        raise ValueError(f"unknown persistent-memory phase: {phase}")

    preferences = _initial_preferences(seed, pressure)
    if phase == "capture":
        protected_paths, expected = _capture_workspace(
            workspace,
            seed=seed,
            pressure=pressure,
            preferences=preferences,
        )
    elif phase == "apply":
        protected_paths, expected = _apply_workspace(
            workspace,
            seed=seed,
            pressure=pressure,
        )
    else:
        protected_paths, expected = _update_workspace(
            workspace,
            seed=seed,
            pressure=pressure,
        )

    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "persistent_memory",
        "scenario": "durable_memory_lifecycle",
        "phase": phase,
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "expected_memory": expected["memory"],
        "expected_report": expected["report"],
        "report_path": expected["report_path"],
        "protected_sha256": _protected(workspace, protected_paths),
    }
    oracle["variant_digest"] = _canonical_digest(oracle)
    return oracle


def _load_json_object(path: Path, label: str) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"{label} missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{label} invalid: {type(exc).__name__}"
    if not isinstance(value, dict):
        return None, f"{label} must be a JSON object"
    return value, None


_CANONICAL_MEMORY_KEYS = frozenset({"schema", "preferences", "history"})
_HISTORY_KEYS = frozenset({"key", "previous", "current"})
_MEMORY_METADATA_KEYS = frozenset({"schema", "authority", "durability_filter", "history"})


def _normalize_history(value: object) -> list[dict[str, str]] | None:
    if value is None:
        return []
    if not isinstance(value, list):
        return None
    rows: list[dict[str, str]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            return None
        key = raw.get("key")
        previous = raw.get("previous")
        current = raw.get("current")
        if not all(isinstance(item, str) for item in (key, previous, current)):
            return None
        rows.append({"key": key, "previous": previous, "current": current})
    return rows


def _semantic_memory_state(
    value: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, bool]:
    raw_preferences = value.get("preferences")
    if isinstance(raw_preferences, Mapping):
        if not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in raw_preferences.items()
        ):
            return None, False
        preferences = dict(raw_preferences)
    elif "preferences" in value:
        return None, False
    elif isinstance(value.get("entries"), list):
        preferences = {}
        for raw in value["entries"]:
            if not isinstance(raw, Mapping):
                return None, False
            key = raw.get("key")
            item = raw.get("value")
            if not isinstance(key, str) or not isinstance(item, str) or key in preferences:
                return None, False
            preferences[key] = item
    elif "entries" in value:
        return None, False
    else:
        preferences = {}
        for key, item in value.items():
            if key in _MEMORY_METADATA_KEYS:
                continue
            if not isinstance(key, str) or not isinstance(item, str):
                return None, False
            preferences[key] = item

    history = _normalize_history(value.get("history", []))
    if history is None:
        return None, False
    canonical_shape = (
        set(value) == _CANONICAL_MEMORY_KEYS
        and value.get("schema") == MEMORY_SCHEMA
        and isinstance(value.get("preferences"), Mapping)
        and isinstance(value.get("history"), list)
        and all(
            isinstance(row, Mapping)
            and set(row) == _HISTORY_KEYS
            and all(isinstance(row.get(key), str) for key in _HISTORY_KEYS)
            for row in value.get("history", [])
        )
    )
    return {
        "preferences": dict(sorted(preferences.items())),
        "history": history,
    }, canonical_shape


def _mapping_accuracy(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> float:
    denominator = max(len(actual), len(expected), 1)
    correct = sum(actual.get(key) == value for key, value in expected.items())
    return correct / denominator


def _history_similarity(
    actual: list[dict[str, str]],
    expected: list[dict[str, str]],
) -> float:
    actual_rows = Counter(
        (row["key"], row["previous"], row["current"])
        for row in actual
    )
    expected_rows = Counter(
        (row["key"], row["previous"], row["current"])
        for row in expected
    )
    if not actual_rows and not expected_rows:
        return 1.0
    if not actual_rows or not expected_rows:
        return 0.0
    overlap = sum((actual_rows & expected_rows).values())
    return 2.0 * overlap / (sum(actual_rows.values()) + sum(expected_rows.values()))


def _normalized_string_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    if len(value) != len(set(value)):
        return None
    return sorted(value)


def _set_similarity(actual: list[str] | None, expected: list[str]) -> float:
    if actual is None:
        return 0.0
    actual_set = set(actual)
    expected_set = set(expected)
    if not actual_set and not expected_set:
        return 1.0
    if not actual_set or not expected_set:
        return 0.0
    return 2.0 * len(actual_set & expected_set) / (len(actual_set) + len(expected_set))


def _report_accuracy(
    phase: str,
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[float, bool]:
    if phase == "capture":
        actual_stored = _normalized_string_list(actual.get("stored_keys"))
        actual_excluded = _normalized_string_list(actual.get("excluded_transient_keys"))
        expected_stored = _normalized_string_list(expected.get("stored_keys")) or []
        expected_excluded = _normalized_string_list(expected.get("excluded_transient_keys")) or []
        score = 0.5 * _set_similarity(actual_stored, expected_stored)
        score += 0.5 * _set_similarity(actual_excluded, expected_excluded)
        exact = (
            set(actual) == set(expected)
            and actual_stored == expected_stored
            and actual_excluded == expected_excluded
        )
        return score, exact

    if phase == "apply":
        actual_applied = actual.get("applied")
        expected_applied = expected.get("applied")
        applied_accuracy = (
            _mapping_accuracy(actual_applied, expected_applied)
            if isinstance(actual_applied, Mapping) and isinstance(expected_applied, Mapping)
            else 0.0
        )
        request_accuracy = 1.0 if actual.get("request_id") == expected.get("request_id") else 0.0
        token_accuracy = (
            1.0
            if actual.get("preference_token") == expected.get("preference_token")
            else 0.0
        )
        score = 0.2 * request_accuracy + 0.2 * token_accuracy + 0.6 * applied_accuracy
        exact = set(actual) == set(expected) and actual == dict(expected)
        return score, exact

    if phase == "update":
        actual_changed = _normalize_history(actual.get("changed"))
        expected_changed = _normalize_history(expected.get("changed")) or []
        changed_accuracy = (
            _history_similarity(actual_changed, expected_changed)
            if actual_changed is not None
            else 0.0
        )
        actual_preserved = actual.get("preserved")
        expected_preserved = expected.get("preserved")
        preserved_accuracy = (
            _mapping_accuracy(actual_preserved, expected_preserved)
            if isinstance(actual_preserved, Mapping) and isinstance(expected_preserved, Mapping)
            else 0.0
        )
        actual_transient = _normalized_string_list(actual.get("transient_ignored"))
        expected_transient = _normalized_string_list(expected.get("transient_ignored")) or []
        transient_accuracy = _set_similarity(actual_transient, expected_transient)
        score = 0.45 * changed_accuracy + 0.35 * preserved_accuracy + 0.20 * transient_accuracy
        exact = (
            set(actual) == set(expected)
            and actual_changed is not None
            and Counter(
                (row["key"], row["previous"], row["current"])
                for row in actual_changed
            )
            == Counter(
                (row["key"], row["previous"], row["current"])
                for row in expected_changed
            )
            and isinstance(actual_preserved, Mapping)
            and dict(actual_preserved) == dict(expected_preserved or {})
            and actual_transient == expected_transient
        )
        return score, exact

    return 0.0, False


def grade_persistent_memory_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
) -> VariantGrade:
    protected = oracle.get("protected_sha256")
    if not isinstance(protected, Mapping):
        return VariantGrade.binary(False, "persistent-memory oracle missing protected hashes")
    for relative, expected in protected.items():
        path = workspace / str(relative)
        if not path.is_file():
            return VariantGrade.binary(False, f"protected source missing: {relative}")
        if _sha256(path) != str(expected):
            return VariantGrade.binary(False, f"protected source modified: {relative}")

    memory, error = _load_json_object(
        workspace / ".agent_memory" / "preferences.json",
        "durable memory",
    )
    if memory is None:
        return VariantGrade.binary(False, str(error))
    expected_memory = oracle.get("expected_memory")
    if not isinstance(expected_memory, Mapping):
        return VariantGrade.binary(False, "persistent-memory oracle missing expected state")

    semantic_memory, canonical_shape = _semantic_memory_state(memory)
    semantic_expected, _ = _semantic_memory_state(expected_memory)
    if semantic_memory is None or semantic_expected is None:
        return VariantGrade.binary(False, "durable memory has an unsupported structure")

    preferences_accuracy = _mapping_accuracy(
        semantic_memory["preferences"],
        semantic_expected["preferences"],
    )
    history_accuracy = _history_similarity(
        semantic_memory["history"],
        semantic_expected["history"],
    )
    semantic_state_matches = (
        semantic_memory["preferences"] == semantic_expected["preferences"]
        and Counter(
            (row["key"], row["previous"], row["current"])
            for row in semantic_memory["history"]
        )
        == Counter(
            (row["key"], row["previous"], row["current"])
            for row in semantic_expected["history"]
        )
    )

    report_path = oracle.get("report_path")
    if not isinstance(report_path, str) or not report_path:
        return VariantGrade.binary(False, "persistent-memory oracle missing report path")
    report, report_error = _load_json_object(workspace / report_path, "memory report")
    expected_report = oracle.get("expected_report")
    if not isinstance(expected_report, Mapping):
        return VariantGrade.binary(False, "persistent-memory oracle missing expected report")
    phase = str(oracle.get("phase", ""))
    if report is None:
        report_accuracy = 0.0
        report_matches = False
    else:
        report_accuracy, report_matches = _report_accuracy(phase, report, expected_report)

    if phase == "capture":
        score = (
            0.55 * preferences_accuracy
            + 0.10 * history_accuracy
            + 0.10 * (1.0 if canonical_shape else 0.0)
            + 0.25 * report_accuracy
        )
    elif phase == "apply":
        score = (
            0.45 * preferences_accuracy
            + 0.10 * history_accuracy
            + 0.10 * (1.0 if canonical_shape else 0.0)
            + 0.35 * report_accuracy
        )
    else:
        score = (
            0.35 * preferences_accuracy
            + 0.25 * history_accuracy
            + 0.10 * (1.0 if canonical_shape else 0.0)
            + 0.30 * report_accuracy
        )

    passed = canonical_shape and semantic_state_matches and report_matches
    metrics = {
        "protected_integrity": 1.0,
        "preference_accuracy": preferences_accuracy,
        "history_accuracy": history_accuracy,
        "schema_conformity": 1.0 if canonical_shape else 0.0,
        "report_accuracy": report_accuracy,
        "semantic_state_matches": semantic_state_matches,
    }
    if passed:
        return VariantGrade(
            True,
            f"persistent memory {phase} phase verified",
            1.0,
            metrics,
        )
    if report is None:
        detail = str(report_error)
    elif not semantic_state_matches:
        detail = "durable memory does not match the required canonical state"
    elif not canonical_shape:
        detail = "durable memory state is correct but canonical schema is not satisfied"
    else:
        detail = "memory report does not match the required application state"
    return VariantGrade(
        passed=False,
        detail=detail,
        score=max(0.0, min(1.0, score)),
        metrics=metrics,
    )


__all__ = [
    "MEMORY_SCHEMA",
    "PersistentMemoryPressure",
    "generate_persistent_memory_variant",
    "grade_persistent_memory_variant",
]
