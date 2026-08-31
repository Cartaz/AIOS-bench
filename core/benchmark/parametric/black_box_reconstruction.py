from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from ..black_box_service import PLANS, REGIONS, TAGS, probe_log_path, reference_transform
from ..failures import VERIFICATION_FAILURE
from ..sandbox import workspace_sandbox
from .grading import VariantGrade


_RULES = (
    "region_offset",
    "plan_multiplier",
    "priority_weight",
    "quantize_units",
    "active_adjustment",
    "tag_bonus",
    "bulk_bonus",
    "premium_bonus",
)


@dataclass(frozen=True)
class BlackBoxReconstructionPressure:
    rule_count: int = 7
    public_examples: int = 12
    probe_budget: int = 48
    distractor_fields: int = 3
    max_units: int = 500

    def __post_init__(self) -> None:
        if not 5 <= self.rule_count <= len(_RULES):
            raise ValueError(f"rule_count must be between 5 and {len(_RULES)}")
        if not 4 <= self.public_examples <= 64:
            raise ValueError("public_examples must be between 4 and 64")
        if not 8 <= self.probe_budget <= 160:
            raise ValueError("probe_budget must be between 8 and 160")
        if not 0 <= self.distractor_fields <= 12:
            raise ValueError("distractor_fields must be between 0 and 12")
        if not 100 <= self.max_units <= 2000:
            raise ValueError("max_units must be between 100 and 2000")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BlackBoxReconstructionPressure":
        allowed = {
            "rule_count",
            "public_examples",
            "probe_budget",
            "distractor_fields",
            "max_units",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(
                f"unknown black-box reconstruction pressure fields: {sorted(unknown)}"
            )
        return cls(**{key: int(raw) for key, raw in value.items()})

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{int(seed)}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reference_spec(seed: int, pressure: BlackBoxReconstructionPressure) -> dict[str, Any]:
    rng = random.Random(_derived_seed(seed, "black-box-spec"))
    multipliers = rng.sample([1, 2, 3, 4, 5], len(PLANS))
    offsets = rng.sample([3, 7, 11, 17, 23, 29], len(REGIONS))
    max_multiplier = max(multipliers)
    high_scale = pressure.max_units * max_multiplier
    low_threshold = max(25, int(high_scale * rng.uniform(0.24, 0.34)))
    high_threshold = max(low_threshold + 25, int(high_scale * rng.uniform(0.58, 0.72)))
    return {
        "schema": "aios-bench/black-box-reference-spec/v1",
        "enabled_rules": list(_RULES[: pressure.rule_count]),
        "max_units": pressure.max_units,
        "region_offsets": dict(zip(REGIONS, offsets, strict=True)),
        "plan_multipliers": dict(zip(PLANS, multipliers, strict=True)),
        "priority_weight": rng.randint(2, 7),
        "round_quantum": rng.choice([5, 10, 20, 25]),
        "active_bonus": rng.randint(7, 31),
        "inactive_penalty": rng.randint(3, 19),
        "special_tag": rng.choice(TAGS),
        "special_tag_bonus": rng.randint(11, 41),
        "bulk_threshold": rng.randint(max(25, pressure.max_units // 4), max(30, pressure.max_units * 3 // 5)),
        "bulk_bonus": rng.randint(13, 47),
        "premium_plan": rng.choice(PLANS),
        "premium_bonus": rng.randint(9, 37),
        "priority_flag_threshold": rng.choice([3, 4, 5]),
        "bucket_thresholds": [low_threshold, high_threshold],
    }


def _record(
    rng: random.Random,
    *,
    max_units: int,
    distractor_fields: int,
    units_low: int = 0,
    units_high: int | None = None,
) -> dict[str, Any]:
    upper = max_units if units_high is None else min(max_units, units_high)
    lower = min(max(0, units_low), upper)
    tags = rng.sample(list(TAGS), rng.randint(0, min(3, len(TAGS))))
    value: dict[str, Any] = {
        "region": rng.choice(REGIONS),
        "plan": rng.choice(PLANS),
        "units": rng.randint(lower, upper),
        "priority": rng.randint(0, 5),
        "active": bool(rng.getrandbits(1)),
        "tags": sorted(tags),
    }
    for index in range(1, distractor_fields + 1):
        value[f"noise_{index:02d}"] = rng.choice(
            [rng.randint(-99, 99), f"decoy-{rng.randint(1, 9)}", bool(rng.getrandbits(1))]
        )
    return value


def _public_examples(
    spec: Mapping[str, Any],
    *,
    seed: int,
    pressure: BlackBoxReconstructionPressure,
) -> list[dict[str, Any]]:
    rng = random.Random(_derived_seed(seed, "black-box-public"))
    public_max = max(25, int(pressure.max_units * 0.58))
    result: list[dict[str, Any]] = []
    for _ in range(pressure.public_examples):
        item = _record(
            rng,
            max_units=pressure.max_units,
            distractor_fields=pressure.distractor_fields,
            units_high=public_max,
        )
        result.append({"input": item, "output": reference_transform(spec, item)})
    return result


def _verification_cases(
    oracle: Mapping[str, Any],
    *,
    transfer: bool,
) -> list[dict[str, Any]]:
    spec = oracle["reference_spec"]
    parameters = oracle["parameters"]
    max_units = int(parameters["max_units"])
    distractors = int(parameters["distractor_fields"])
    seed_key = "transfer_seed" if transfer else "verification_seed"
    rng = random.Random(int(oracle[seed_key]))
    count = 64 if transfer else 96
    result: list[dict[str, Any]] = []

    if not transfer:
        quantum = int(spec["round_quantum"])
        bulk = int(spec["bulk_threshold"])
        boundary_units = sorted(
            {
                0,
                1,
                max(0, quantum - 1),
                quantum,
                min(max_units, quantum + 1),
                max(0, bulk - 1),
                min(max_units, bulk),
                min(max_units, bulk + 1),
                max_units,
            }
        )
        for index, units in enumerate(boundary_units):
            item = _record(
                rng,
                max_units=max_units,
                distractor_fields=distractors,
            )
            item["units"] = units
            item["region"] = REGIONS[index % len(REGIONS)]
            item["plan"] = PLANS[index % len(PLANS)]
            item["priority"] = index % 6
            result.append(item)

    lower = int(max_units * 0.60) if transfer else 0
    while len(result) < count:
        item = _record(
            rng,
            max_units=max_units,
            distractor_fields=distractors,
            units_low=lower,
        )
        if transfer:
            # Transfer cases deliberately combine high-range inputs with tag and
            # activity interactions underrepresented in public examples.
            item["active"] = len(result) % 3 != 0
            if len(result) % 2 == 0:
                special = str(spec["special_tag"])
                item["tags"] = sorted(set([*item["tags"], special]))
        result.append(item)
    return result[:count]


def generate_black_box_reconstruction_variant(
    workspace: Path,
    *,
    seed: int,
    pressure: BlackBoxReconstructionPressure,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "docs").mkdir(parents=True, exist_ok=True)
    (workspace / "examples").mkdir(parents=True, exist_ok=True)
    (workspace / "solution").mkdir(parents=True, exist_ok=True)

    spec = _reference_spec(seed, pressure)
    examples = _public_examples(spec, seed=seed, pressure=pressure)
    readme = workspace / "README.md"
    readme.write_text(
        "# Black-box compatibility reconstruction\n\n"
        "Reconstruct the behavior of a hidden deterministic JSON transformer. There is no "
        "reference implementation in the workspace. Read `docs/contract.md` and the observed "
        "examples in `examples/public_examples.jsonl`. While the task is running you may query "
        "the bounded reference service with `python tools/reference_api.py contract` and "
        "`python tools/reference_api.py probe --input '{...}'`.\n\n"
        "Create `solution/reconstruct.py`. At evaluation time it will receive UTF-8 JSONL on "
        "stdin, one valid input object per line, and must emit exactly one JSON object per input "
        "line on stdout in the same order. Do not print commentary to stdout. Hidden property "
        "tests include boundary combinations and transfer inputs outside the public-example "
        "distribution. The reference API is stopped before hidden verification.\n",
        encoding="utf-8",
    )
    contract = workspace / "docs" / "contract.md"
    contract.write_text(
        "# Public compatibility contract\n\n"
        f"Inputs require `region` in {list(REGIONS)}, `plan` in {list(PLANS)}, integer `units` "
        f"from 0 through {pressure.max_units}, integer `priority` from 0 through 5, boolean "
        f"`active`, and a duplicate-free `tags` array drawn from {list(TAGS)}. Unknown fields "
        "are accepted and ignored.\n\n"
        "Outputs contain exactly `bucket`, `score`, `normalized_units`, and `flags`. `bucket` is "
        "one of `low`, `standard`, or `high`; the two numeric fields are non-negative integers; "
        "`flags` is a sorted unique array of strings. The function is deterministic and stateless. "
        "Seeded internal rules/constants are intentionally undocumented and must be inferred from "
        "observed behavior.\n\n"
        f"The live probe budget for this variant is {pressure.probe_budget} successful probes.\n",
        encoding="utf-8",
    )
    examples_path = workspace / "examples" / "public_examples.jsonl"
    examples_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in examples),
        encoding="utf-8",
    )

    protected = ["README.md", "docs/contract.md", "examples/public_examples.jsonl"]
    oracle: dict[str, Any] = {
        "schema": "aios-bench/parametric-oracle/v1",
        "family": "black_box_reconstruction",
        "scenario": "json_transformer_reconstruction",
        "seed": int(seed),
        "parameters": pressure.to_dict(),
        "reference_spec": spec,
        "probe_budget": pressure.probe_budget,
        "verification_seed": _derived_seed(seed, "black-box-hidden-properties"),
        "transfer_seed": _derived_seed(seed, "black-box-transfer"),
        "verification_case_count": 96,
        "transfer_case_count": 64,
        "solution_path": "solution/reconstruct.py",
        "protected_sha256": {
            relative: _sha256(workspace / relative)
            for relative in protected
        },
    }
    oracle["variant_digest"] = _digest(oracle)
    return oracle


def _run_solution(
    workspace: Path,
    solution: Path,
    cases: list[dict[str, Any]],
) -> tuple[int, str, str, bool]:
    plan = workspace_sandbox("blackbox-verifier", workspace)
    if not plan.grader_hidden:
        return 126, "", "grader-hidden bubblewrap sandbox unavailable", False
    payload = "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in cases)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONHASHSEED": "0",
    }
    base_executable = getattr(sys, "_base_executable", None) or sys.executable
    verification_python = Path(base_executable).resolve()
    try:
        process = subprocess.run(
            plan.wrap([str(verification_python), "-I", str(solution.relative_to(workspace))]),
            cwd=workspace,
            input=payload,
            text=True,
            capture_output=True,
            timeout=15,
            env=env,
            check=False,
        )
        return process.returncode, process.stdout, process.stderr[-4000:], True
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return 124, stdout, (stderr + "\nverification timeout")[-4000:], True
    except OSError as exc:
        return 126, "", f"{type(exc).__name__}: {exc}", True


def _parse_outputs(stdout: str, expected_count: int) -> tuple[list[dict[str, Any] | None], int]:
    lines = stdout.splitlines()
    invalid = abs(len(lines) - expected_count)
    parsed: list[dict[str, Any] | None] = []
    for line in lines[:expected_count]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            parsed.append(None)
            invalid += 1
            continue
        if not isinstance(value, dict) or set(value) != {
            "bucket",
            "score",
            "normalized_units",
            "flags",
        }:
            parsed.append(None)
            invalid += 1
            continue
        parsed.append(value)
    while len(parsed) < expected_count:
        parsed.append(None)
    return parsed, invalid


def _score_outputs(
    spec: Mapping[str, Any],
    cases: list[dict[str, Any]],
    outputs: list[dict[str, Any] | None],
) -> tuple[int, int, int]:
    exact = 0
    correct_fields = 0
    total_fields = len(cases) * 4
    for case, output in zip(cases, outputs, strict=True):
        expected = reference_transform(spec, case)
        if output == expected:
            exact += 1
        if output is None:
            continue
        correct_fields += sum(output.get(field) == expected[field] for field in expected)
    return exact, correct_fields, total_fields


def _probe_count(run_dir: Path | None, task_id: str | None) -> int:
    if run_dir is None or not task_id:
        return 0
    path = probe_log_path(run_dir, task_id)
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def grade_black_box_reconstruction_variant(
    workspace: Path,
    oracle: Mapping[str, Any],
    *,
    run_dir: Path | None = None,
    task_id: str | None = None,
) -> VariantGrade:
    try:
        if oracle.get("family") != "black_box_reconstruction":
            return VariantGrade.binary(False, "black-box oracle family mismatch")
        if oracle.get("scenario") != "json_transformer_reconstruction":
            return VariantGrade.binary(False, "unknown black-box reconstruction scenario")

        protected = oracle.get("protected_sha256")
        if not isinstance(protected, Mapping):
            return VariantGrade.binary(False, "black-box protected-source manifest missing")
        for relative, expected in protected.items():
            path = workspace / str(relative)
            if not path.is_file() or _sha256(path) != str(expected):
                return VariantGrade.binary(False, f"protected source modified: {relative}")

        solution = workspace / str(oracle.get("solution_path", ""))
        if not solution.is_file():
            return VariantGrade(
                False,
                "black-box implementation missing",
                0.0,
                metrics={"probe_count": _probe_count(run_dir, task_id)},
                failure_kind=VERIFICATION_FAILURE,
            )
        spec = oracle.get("reference_spec")
        if not isinstance(spec, Mapping):
            return VariantGrade.binary(False, "black-box reference specification missing")

        property_cases = _verification_cases(oracle, transfer=False)
        transfer_cases = _verification_cases(oracle, transfer=True)
        cases = [*property_cases, *transfer_cases]
        returncode, stdout, stderr, sandboxed = _run_solution(workspace, solution, cases)
        outputs, protocol_errors = _parse_outputs(stdout, len(cases))
        property_outputs = outputs[: len(property_cases)]
        transfer_outputs = outputs[len(property_cases) :]
        property_exact, property_fields, property_total_fields = _score_outputs(
            spec, property_cases, property_outputs
        )
        transfer_exact, transfer_fields, transfer_total_fields = _score_outputs(
            spec, transfer_cases, transfer_outputs
        )
        exact = property_exact + transfer_exact
        total = len(cases)
        field_correct = property_fields + transfer_fields
        field_total = property_total_fields + transfer_total_fields
        property_accuracy = property_exact / len(property_cases)
        transfer_accuracy = transfer_exact / len(transfer_cases)
        exact_accuracy = exact / total
        field_accuracy = field_correct / field_total if field_total else 0.0
        passed = (
            sandboxed
            and returncode == 0
            and protocol_errors == 0
            and property_exact == len(property_cases)
            and transfer_exact == len(transfer_cases)
        )
        metrics = {
            "property_accuracy": property_accuracy,
            "transfer_accuracy": transfer_accuracy,
            "exact_case_accuracy": exact_accuracy,
            "output_field_accuracy": field_accuracy,
            "property_cases": len(property_cases),
            "transfer_cases": len(transfer_cases),
            "protocol_error_count": protocol_errors,
            "implementation_returncode": returncode,
            "verifier_sandboxed": sandboxed,
            "probe_count": _probe_count(run_dir, task_id),
            "probe_budget": int(oracle.get("probe_budget", 0)),
        }
        if passed:
            return VariantGrade(
                True,
                "black-box hidden property and transfer suites verified",
                1.0,
                metrics=metrics,
            )
        detail = (
            "black-box hidden verification failed: "
            f"property={property_exact}/{len(property_cases)}, "
            f"transfer={transfer_exact}/{len(transfer_cases)}, "
            f"protocol_errors={protocol_errors}, returncode={returncode}"
        )
        if stderr:
            detail += f"; stderr={stderr[-600:]}"
        return VariantGrade(
            False,
            detail,
            exact_accuracy,
            metrics=metrics,
            failure_kind=VERIFICATION_FAILURE,
        )
    except (OSError, TypeError, ValueError, KeyError) as exc:
        return VariantGrade(
            False,
            f"black-box reconstruction oracle error: {type(exc).__name__}: {exc}",
            0.0,
            failure_kind=VERIFICATION_FAILURE,
        )


__all__ = [
    "BlackBoxReconstructionPressure",
    "generate_black_box_reconstruction_variant",
    "grade_black_box_reconstruction_variant",
]
