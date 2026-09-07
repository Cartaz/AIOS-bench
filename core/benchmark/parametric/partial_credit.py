from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from ..reference_checks_core import eval_path
from .grading import VariantGrade


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _ratio(correct: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return _clamp(correct / total)


def _weighted(parts: Mapping[str, tuple[float, float]]) -> float:
    total_weight = sum(weight for weight, _ in parts.values())
    if total_weight <= 0:
        return 0.0
    return _clamp(
        sum(weight * _clamp(value) for weight, value in parts.values()) / total_weight
    )


def _set_similarity(actual: set[str], expected: set[str]) -> float:
    if not actual and not expected:
        return 1.0
    if not actual or not expected:
        return 0.0
    return _clamp(2.0 * len(actual & expected) / (len(actual) + len(expected)))


def _mapping_accuracy(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> float:
    if not actual and not expected:
        return 1.0
    denominator = max(len(actual), len(expected), 1)
    correct = sum(actual.get(key) == value for key, value in expected.items())
    return _ratio(correct, denominator)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _protected_integrity(workspace: Path, oracle: Mapping[str, Any]) -> float:
    protected = oracle.get("protected_sha256")
    if not isinstance(protected, Mapping) or not protected:
        return 0.0
    correct = 0
    for relative, expected in protected.items():
        path = workspace / str(relative)
        try:
            if path.is_file() and _sha256(path) == str(expected):
                correct += 1
        except OSError:
            continue
    return _ratio(correct, len(protected))


def _grade(
    *,
    passed: bool,
    detail: str,
    parts: Mapping[str, tuple[float, float]],
    failure_kind: str | None = None,
    extra_metrics: Mapping[str, Any] | None = None,
) -> VariantGrade:
    metrics: dict[str, Any] = {
        key: _clamp(value)
        for key, (_, value) in parts.items()
    }
    if extra_metrics:
        metrics.update(dict(extra_metrics))
    score = 1.0 if passed else _weighted(parts)
    return VariantGrade(
        passed=passed,
        detail=detail,
        score=score,
        metrics=metrics,
        failure_kind=failure_kind,
    )


def grade_config_traversal_partial(
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    passed: bool,
    detail: str,
) -> VariantGrade:
    report = workspace / "reports" / "effective_config.md"
    if not report.is_file():
        return VariantGrade(passed, detail, 1.0 if passed else 0.0, {"report_valid": False})
    try:
        text = report.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return VariantGrade(passed, detail, 1.0 if passed else 0.0, {"report_valid": False})

    settings = oracle.get("settings")
    chain = oracle.get("reference_chain")
    if not isinstance(settings, Mapping) or not isinstance(chain, list):
        return VariantGrade(passed, detail, 1.0 if passed else 0.0, {"oracle_valid": False})

    settings_correct = 0
    for key, value in settings.items():
        pattern = rf"\b{re.escape(str(key))}\b\s*[:=]\s*{re.escape(str(value))}(?!\w)"
        settings_correct += re.search(pattern, text, re.I) is not None

    ordered_found = 0
    position = -1
    for relative in chain:
        next_position = text.find(str(relative), position + 1)
        if next_position >= 0:
            ordered_found += 1
            position = next_position

    decoys = [str(value) for value in oracle.get("decoy_ports") or []]
    decoys_avoided = sum(
        re.search(rf"\bport\b\s*[:=]\s*{re.escape(value)}\b", text, re.I) is None
        for value in decoys
    )
    consumer = str(oracle.get("consumer_path", ""))
    parts = {
        "protected_integrity": (0.10, _protected_integrity(workspace, oracle)),
        "settings_accuracy": (0.50, _ratio(settings_correct, len(settings))),
        "reference_chain_accuracy": (0.20, _ratio(ordered_found, len(chain))),
        "consumer_reference": (0.10, 1.0 if consumer and consumer in text else 0.0),
        "distractor_avoidance": (0.10, _ratio(decoys_avoided, len(decoys))),
    }
    return _grade(passed=passed, detail=detail, parts=parts)


def _expense_text_accuracy(text: str, section: Mapping[str, Any]) -> float:
    totals = section.get("monthly_totals")
    if not isinstance(totals, Mapping):
        return 0.0
    correct = 0
    total = len(totals) + 1
    for month, amount in totals.items():
        if str(month) in text and str(amount) in text:
            correct += 1
    try:
        malformed = int(section.get("malformed_rows", -1))
    except (TypeError, ValueError):
        malformed = -1
    malformed_pattern = re.compile(
        rf"(?:skipped|malformed|invalid).{{0,50}}\b{malformed}\b",
        re.IGNORECASE | re.DOTALL,
    )
    if malformed >= 0 and malformed_pattern.search(text) is not None:
        correct += 1
    return _ratio(correct, total)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
    except OSError:
        return None


def grade_expense_partial(
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    passed: bool,
    detail: str,
) -> VariantGrade:
    tool = workspace / "tools" / "expense_report.py"
    saved = _read_text(workspace / "reports" / "monthly_expense_report.md")
    if not tool.is_file() or saved is None:
        return VariantGrade(
            passed,
            detail,
            1.0 if passed else 0.0,
            {"required_artifacts_present": False},
        )

    primary = oracle.get("primary")
    alternate = oracle.get("alternate")
    if not isinstance(primary, Mapping) or not isinstance(alternate, Mapping):
        return VariantGrade(passed, detail, 1.0 if passed else 0.0, {"oracle_valid": False})

    generated_primary = _read_text(eval_path(workspace, "v4_expense_primary.md"))
    generated_alternate = _read_text(eval_path(workspace, "v4_expense_alternate.md"))
    source = _read_text(tool) or ""
    totals = {
        str(value)
        for section in (primary, alternate)
        for value in (section.get("monthly_totals") or {}).values()
    }
    hardcoded_clean = not any(total and total in source for total in totals)
    parts = {
        "protected_integrity": (0.10, _protected_integrity(workspace, oracle)),
        "saved_report_accuracy": (0.25, _expense_text_accuracy(saved, primary)),
        "primary_execution_accuracy": (
            0.25,
            0.0 if generated_primary is None else _expense_text_accuracy(generated_primary, primary),
        ),
        "transfer_execution_accuracy": (
            0.25,
            0.0 if generated_alternate is None else _expense_text_accuracy(generated_alternate, alternate),
        ),
        "fixture_independence": (0.15, 1.0 if hardcoded_clean else 0.0),
    }
    return _grade(passed=passed, detail=detail, parts=parts)


def _normalize_lineage_paths(value: Any) -> set[tuple[str, ...]]:
    if not isinstance(value, list):
        return set()
    result: set[tuple[str, ...]] = set()
    for raw in value:
        if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
            result.add(tuple(raw))
    return result


def grade_workspace_lineage_partial(
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    passed: bool,
    detail: str,
) -> VariantGrade:
    path = workspace / "reports" / "workspace_lineage.json"
    try:
        report = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, json.JSONDecodeError):
        report = None
    if not isinstance(report, Mapping):
        return VariantGrade(passed, detail, 1.0 if passed else 0.0, {"report_valid": False})

    scalar_fields = ("active_release", "root", "consumer_path")
    scalar_correct = sum(report.get(field) == oracle.get(field) for field in scalar_fields)
    actual_paths = _normalize_lineage_paths(report.get("lineage_paths"))
    expected_paths = _normalize_lineage_paths(oracle.get("lineage_paths"))
    actual_settings = report.get("effective_settings")
    expected_settings = oracle.get("effective_settings")
    settings_accuracy = (
        _mapping_accuracy(actual_settings, expected_settings)
        if isinstance(actual_settings, Mapping) and isinstance(expected_settings, Mapping)
        else 0.0
    )
    actual_stale = {
        str(value)
        for value in report.get("ignored_stale_sources", [])
        if isinstance(value, str)
    } if isinstance(report.get("ignored_stale_sources"), list) else set()
    expected_stale = {str(value) for value in oracle.get("stale_source_paths") or []}
    parts = {
        "protected_integrity": (0.10, _protected_integrity(workspace, oracle)),
        "release_identity": (0.15, _ratio(scalar_correct, len(scalar_fields))),
        "lineage_path_accuracy": (
            0.25,
            _set_similarity(
                {"\u241f".join(path) for path in actual_paths},
                {"\u241f".join(path) for path in expected_paths},
            ),
        ),
        "effective_settings_accuracy": (0.30, settings_accuracy),
        "stale_source_inventory": (0.20, _set_similarity(actual_stale, expected_stale)),
    }
    return _grade(passed=passed, detail=detail, parts=parts)


def _sqlite_rows(database: Path, table: str) -> dict[str, dict[str, Any]]:
    if not database.is_file():
        return {}
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        return {
            str(row["id"]): {key: row[key] for key in row.keys()}
            for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY id')
        }


def _sqlite_schema_accuracy(database: Path, expected: Any) -> float:
    if not database.is_file():
        return 0.0
    try:
        with sqlite3.connect(database) as connection:
            if isinstance(expected, Mapping):
                correct = 0
                for table, sql in expected.items():
                    row = connection.execute(
                        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                        (str(table),),
                    ).fetchone()
                    if row is not None and str(row[0]) == str(sql):
                        correct += 1
                return _ratio(correct, len(expected))
            row = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='tickets'"
            ).fetchone()
            return 1.0 if row is not None and str(row[0]) == str(expected) else 0.0
    except sqlite3.Error:
        return 0.0


def _rows_from_oracle(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    return {
        str(row["id"]): dict(row)
        for row in value
        if isinstance(row, Mapping) and row.get("id") is not None
    }


def _world_accuracy_parts(
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    dependency: bool,
    provenance_ok: bool,
) -> dict[str, tuple[float, float]]:
    database = workspace / str(oracle.get("database_path", ""))
    baseline = _rows_from_oracle(oracle.get("baseline_rows"))
    current: dict[str, dict[str, Any]] = {}
    try:
        current = _sqlite_rows(database, "tickets")
    except sqlite3.Error:
        pass
    expected_mutations = oracle.get("expected_mutations")
    if not isinstance(expected_mutations, Mapping):
        expected_mutations = {}
    mutable_fields = {"priority", "assignee", "escalation_reason"}

    target_mutable_correct = 0
    target_mutable_total = 0
    target_immutable_correct = 0
    target_immutable_total = 0
    non_target_correct = 0
    non_target_total = 0
    for ticket_id, before in baseline.items():
        after = current.get(ticket_id)
        mutation = expected_mutations.get(ticket_id)
        if mutation is None:
            non_target_total += 1
            non_target_correct += after == before
            continue
        if not isinstance(mutation, Mapping) or after is None:
            target_mutable_total += len(mutable_fields)
            target_immutable_total += len([key for key in before if key not in mutable_fields])
            continue
        for field in mutable_fields:
            target_mutable_total += 1
            target_mutable_correct += after.get(field) == mutation.get(field)
        for field, value in before.items():
            if field in mutable_fields:
                continue
            target_immutable_total += 1
            target_immutable_correct += after.get(field) == value

    report = _read_text(workspace / "reports" / "escalation_summary.md") or ""
    reported_ids = set(re.findall(r"\bTKT-\d{4}\b", report))
    expected_ids = {str(value) for value in oracle.get("target_ids") or []}
    schema_accuracy = _sqlite_schema_accuracy(database, oracle.get("schema_sql"))
    row_set_accuracy = _set_similarity(set(current), set(baseline))

    if dependency:
        baseline_accounts = _rows_from_oracle(oracle.get("baseline_accounts"))
        try:
            current_accounts = _sqlite_rows(database, "accounts")
        except sqlite3.Error:
            current_accounts = {}
        account_accuracy = _ratio(
            sum(current_accounts.get(key) == value for key, value in baseline_accounts.items()),
            max(len(baseline_accounts), len(current_accounts), 1),
        )
        return {
            "protected_integrity": (0.10, _protected_integrity(workspace, oracle)),
            "schema_and_row_set": (0.10, (schema_accuracy + row_set_accuracy) / 2.0),
            "target_mutation_accuracy": (
                0.30,
                _ratio(target_mutable_correct, target_mutable_total),
            ),
            "target_immutable_preservation": (
                0.08,
                _ratio(target_immutable_correct, target_immutable_total),
            ),
            "non_target_preservation": (0.15, _ratio(non_target_correct, non_target_total)),
            "account_preservation": (0.12, account_accuracy),
            "report_accuracy": (0.10, _set_similarity(reported_ids, expected_ids)),
            "action_provenance": (0.05, 1.0 if provenance_ok else 0.0),
        }

    return {
        "protected_integrity": (0.10, _protected_integrity(workspace, oracle)),
        "schema_and_row_set": (0.10, (schema_accuracy + row_set_accuracy) / 2.0),
        "target_mutation_accuracy": (
            0.35,
            _ratio(target_mutable_correct, target_mutable_total),
        ),
        "target_immutable_preservation": (
            0.10,
            _ratio(target_immutable_correct, target_immutable_total),
        ),
        "non_target_preservation": (0.20, _ratio(non_target_correct, non_target_total)),
        "report_accuracy": (0.10, _set_similarity(reported_ids, expected_ids)),
        "action_provenance": (0.05, 1.0 if provenance_ok else 0.0),
    }


def grade_stateful_world_partial(
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    passed: bool,
    detail: str,
    provenance_ok: bool,
) -> VariantGrade:
    return _grade(
        passed=passed,
        detail=detail,
        parts=_world_accuracy_parts(
            workspace,
            oracle,
            dependency=False,
            provenance_ok=provenance_ok,
        ),
    )


def grade_dependency_world_partial(
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    passed: bool,
    detail: str,
    provenance_ok: bool,
) -> VariantGrade:
    return _grade(
        passed=passed,
        detail=detail,
        parts=_world_accuracy_parts(
            workspace,
            oracle,
            dependency=True,
            provenance_ok=provenance_ok,
        ),
    )


def grade_tool_recovery_partial(
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    passed: bool,
    detail: str,
    provenance_ok: bool,
    failure_kind: str | None,
) -> VariantGrade:
    baseline = _rows_from_oracle(oracle.get("baseline_cases"))
    state_path = workspace / str(oracle.get("state_path", ""))
    current: dict[str, dict[str, Any]] = {}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else None
        raw_cases = state.get("cases") if isinstance(state, Mapping) else None
        current = _rows_from_oracle(raw_cases)
    except (OSError, json.JSONDecodeError):
        current = {}

    targets = {str(value) for value in oracle.get("target_ids") or []}
    mutable = {"processed", "process_count"}
    target_state_correct = 0
    target_state_total = 2 * len(targets)
    target_immutable_correct = 0
    target_immutable_total = 0
    non_target_correct = 0
    non_target_total = 0
    for case_id, before in baseline.items():
        after = current.get(case_id)
        if case_id in targets:
            if after is not None:
                target_state_correct += after.get("processed") is True
                target_state_correct += after.get("process_count") == 1
            for field, value in before.items():
                if field in mutable:
                    continue
                target_immutable_total += 1
                if after is not None:
                    target_immutable_correct += after.get(field) == value
        else:
            non_target_total += 1
            non_target_correct += after == before

    report_path = workspace / "reports" / "tool_recovery_summary.json"
    processed: set[str] = set()
    recovered: set[str] = set()
    try:
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
        if isinstance(report, Mapping):
            if isinstance(report.get("processed_case_ids"), list):
                processed = {str(value) for value in report["processed_case_ids"]}
            if isinstance(report.get("recovered_case_ids"), list):
                recovered = {str(value) for value in report["recovered_case_ids"]}
    except (OSError, json.JSONDecodeError):
        pass
    expected_recovered = {
        str(value) for value in oracle.get("ambiguous_write_case_ids") or []
    }
    parts = {
        "protected_integrity": (0.10, _protected_integrity(workspace, oracle)),
        "case_set_accuracy": (0.05, _set_similarity(set(current), set(baseline))),
        "target_process_accuracy": (
            0.30,
            _ratio(target_state_correct, target_state_total),
        ),
        "target_immutable_preservation": (
            0.10,
            _ratio(target_immutable_correct, target_immutable_total),
        ),
        "non_target_preservation": (0.15, _ratio(non_target_correct, non_target_total)),
        "processed_report_accuracy": (0.10, _set_similarity(processed, targets)),
        "recovered_report_accuracy": (
            0.05,
            _set_similarity(recovered, expected_recovered),
        ),
        "recovery_provenance": (0.15, 1.0 if provenance_ok else 0.0),
    }
    return _grade(
        passed=passed,
        detail=detail,
        parts=parts,
        failure_kind=failure_kind,
    )


__all__ = [
    "grade_config_traversal_partial",
    "grade_dependency_world_partial",
    "grade_expense_partial",
    "grade_stateful_world_partial",
    "grade_tool_recovery_partial",
    "grade_workspace_lineage_partial",
]
