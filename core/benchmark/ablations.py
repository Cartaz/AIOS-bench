from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from typing import Any, Iterable


SKILL_ABLATION_SCHEMA = "aios-bench/skill-ablation/v1"
_SKILL_MODES = ("no_skill", "curated_skill")


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _params(row: dict[str, Any]) -> dict[str, Any] | None:
    value = row.get("variant_parameters")
    if not isinstance(value, dict) or not value:
        return None
    normalized: dict[str, Any] = {}
    for key, raw in sorted(value.items(), key=lambda item: str(item[0])):
        if isinstance(raw, (bool, int, str)):
            normalized[str(key)] = raw
        elif isinstance(raw, float) and math.isfinite(raw):
            normalized[str(key)] = raw
        else:
            normalized[str(key)] = str(raw)
    return normalized


def _vector_key(parameters: dict[str, Any]) -> str:
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _row_key(row: dict[str, Any]) -> tuple[int, str, int, str, str] | None:
    parameters = _params(row)
    if parameters is None or not row.get("variant_digest"):
        return None
    try:
        return (
            int(row["repeat"]),
            str(row["task_id"]),
            int(row["task_seed"]),
            str(row["variant_digest"]),
            _vector_key(parameters),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _pair_rejection(
    no_skill: list[dict[str, Any]],
    curated: list[dict[str, Any]],
) -> str | None:
    model_ids = {
        str(row["model_identity_fingerprint"])
        for row in [*no_skill, *curated]
        if row.get("model_identity_fingerprint")
    }
    if len(model_ids) != 1:
        return "model_identity_mismatch_or_unverified"
    if not all(bool(row.get("model_strictly_comparable")) for row in [*no_skill, *curated]):
        return "strict_model_comparability_missing"
    profiles = {
        str(row["ablation_execution_fingerprint"])
        for row in [*no_skill, *curated]
        if row.get("ablation_execution_fingerprint")
    }
    if len(profiles) != 1:
        return "ablation_execution_profile_mismatch"
    skill_ids = {str(row.get("skill_id")) for row in [*no_skill, *curated]}
    skill_digests = {str(row.get("skill_digest")) for row in [*no_skill, *curated]}
    if len(skill_ids) != 1 or "None" in skill_ids:
        return "curated_skill_identity_missing"
    if len(skill_digests) != 1 or "None" in skill_digests:
        return "curated_skill_digest_mismatch"
    return None


def skill_ablation_pairs(
    rows: Iterable[dict[str, Any]],
    *,
    suite: str | None = None,
    suite_revision: str | None = None,
) -> list[dict[str, Any]]:
    """Measure curated-skill lift only inside exact matched experiment cells.

    The two arms deliberately have different ordinary execution fingerprints.
    They may pair only when the pressure vector, generated variant, task seed,
    model identity, skill package and the execution profile with skill_mode
    neutralized are all identical.
    """
    groups: dict[
        tuple[str, str, str, str, str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)
    for row in rows:
        if suite is not None and str(row.get("suite")) != suite:
            continue
        if suite_revision is not None and str(row.get("suite_revision")) != suite_revision:
            continue
        if row.get("schedule_mode") != "matched_interleaved" or not row.get("experiment_id"):
            continue
        if row.get("skill_mode") not in _SKILL_MODES or not row.get("skill_available"):
            continue
        if not row.get("task_id") or not row.get("variant_family"):
            continue
        key = (
            str(row["experiment_id"]),
            str(row.get("harness", row.get("agent", "unknown"))),
            str(row.get("model", "unknown")),
            str(row.get("suite", "legacy")),
            str(row.get("suite_revision", "legacy")),
            str(row.get("variant_family")),
        )
        groups[key].append(row)

    output: list[dict[str, Any]] = []
    for group_key, items in sorted(groups.items()):
        arms = {
            mode: [row for row in items if row.get("skill_mode") == mode]
            for mode in _SKILL_MODES
        }
        if not arms["no_skill"] or not arms["curated_skill"]:
            continue

        base = {
            "schema": SKILL_ABLATION_SCHEMA,
            "experiment_id": group_key[0],
            "harness": group_key[1],
            "model": group_key[2],
            "suite": group_key[3],
            "suite_revision": group_key[4],
            "variant_family": group_key[5],
        }
        rejection = _pair_rejection(arms["no_skill"], arms["curated_skill"])
        if rejection is not None:
            output.append({
                **base,
                "comparable": False,
                "reason": rejection,
                "matched_observations": 0,
            })
            continue

        def indexed(source: list[dict[str, Any]]) -> dict[tuple[int, str, int, str, str], dict[str, Any]]:
            result: dict[tuple[int, str, int, str, str], dict[str, Any]] = {}
            for row in source:
                if row.get("status") == "unsupported" or row.get("comparable") is False:
                    continue
                if _number(row.get("score")) is None:
                    continue
                key = _row_key(row)
                if key is not None:
                    result[key] = row
            return result

        no_index = indexed(arms["no_skill"])
        curated_index = indexed(arms["curated_skill"])
        matched = sorted(set(no_index) & set(curated_index))

        score_lifts: list[float] = []
        input_token_lifts: list[float] = []
        output_token_lifts: list[float] = []
        curated_wins = no_skill_wins = ties = 0
        curated_only_pass = no_skill_only_pass = 0
        cells: list[dict[str, Any]] = []
        for match in matched:
            no_row = no_index[match]
            curated_row = curated_index[match]
            no_score = float(no_row["score"])
            curated_score = float(curated_row["score"])
            lift = curated_score - no_score
            score_lifts.append(lift)
            if lift > 0:
                curated_wins += 1
            elif lift < 0:
                no_skill_wins += 1
            else:
                ties += 1
            if bool(curated_row.get("success")) and not bool(no_row.get("success")):
                curated_only_pass += 1
            if bool(no_row.get("success")) and not bool(curated_row.get("success")):
                no_skill_only_pass += 1
            no_input = _number(no_row.get("input_tokens"))
            curated_input = _number(curated_row.get("input_tokens"))
            if no_input is not None and curated_input is not None:
                input_token_lifts.append(curated_input - no_input)
            no_output = _number(no_row.get("output_tokens"))
            curated_output = _number(curated_row.get("output_tokens"))
            if no_output is not None and curated_output is not None:
                output_token_lifts.append(curated_output - no_output)
            cells.append({
                "repeat": match[0],
                "task_id": match[1],
                "task_seed": match[2],
                "variant_digest": match[3],
                "parameters": _params(no_row),
                "no_skill_score": no_score,
                "curated_skill_score": curated_score,
                "skill_lift": lift,
                "no_skill_pass": bool(no_row.get("success")),
                "curated_skill_pass": bool(curated_row.get("success")),
            })

        sample = arms["curated_skill"][0]
        no_fingerprints = sorted({
            str(row["execution_fingerprint"])
            for row in arms["no_skill"]
            if row.get("execution_fingerprint")
        })
        curated_fingerprints = sorted({
            str(row["execution_fingerprint"])
            for row in arms["curated_skill"]
            if row.get("execution_fingerprint")
        })
        output.append({
            **base,
            "comparable": True,
            "model_identity_fingerprint": sample.get("model_identity_fingerprint"),
            "ablation_execution_fingerprint": sample.get("ablation_execution_fingerprint"),
            "skill_id": sample.get("skill_id"),
            "skill_digest": sample.get("skill_digest"),
            "no_skill_execution_fingerprints": no_fingerprints,
            "curated_skill_execution_fingerprints": curated_fingerprints,
            "matched_observations": len(matched),
            "mean_skill_lift": sum(score_lifts) / len(score_lifts) if score_lifts else None,
            "median_skill_lift": statistics.median(score_lifts) if score_lifts else None,
            "curated_wins": curated_wins,
            "no_skill_wins": no_skill_wins,
            "ties": ties,
            "curated_pass_no_skill_fail": curated_only_pass,
            "no_skill_pass_curated_fail": no_skill_only_pass,
            "mean_input_token_delta": (
                sum(input_token_lifts) / len(input_token_lifts) if input_token_lifts else None
            ),
            "mean_output_token_delta": (
                sum(output_token_lifts) / len(output_token_lifts) if output_token_lifts else None
            ),
            "cells": cells,
        })
    return output


__all__ = ["SKILL_ABLATION_SCHEMA", "skill_ablation_pairs"]
