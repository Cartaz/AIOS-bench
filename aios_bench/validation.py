from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from .evaluators import evaluate_artifacts
from .experiments import derive_seed
from .fixtures import materialize_long_horizon_corpus
from .parametric import materialize_variant


def _checks(repo_root: Path, task: object) -> list[dict[str, Any]]:
    checks = list(getattr(task, "acceptance", ()) or ())
    spec = repo_root / "benchmarks" / "tasks" / "specs" / f"{getattr(task, 'id')}.json"
    if not checks and spec.is_file():
        checks = json.loads(spec.read_text(encoding="utf-8"))["checks"]
    return checks


def validate_negative_baseline(repo_root: Path, tasks: Iterable[object]) -> dict[str, Any]:
    """Fail if an untouched static fixture can already satisfy a deterministic grader."""
    fixture_root = repo_root / "benchmarks" / "fixtures" / "workspace"
    failures: list[dict[str, Any]] = []
    checked = 0
    with tempfile.TemporaryDirectory(prefix="aios-bench-validate-") as temporary:
        root = Path(temporary)
        for task in tasks:
            checks = _checks(repo_root, task)
            task_id = str(getattr(task, "id"))
            if not checks:
                failures.append({"task_id": task_id, "reason": "no deterministic checks"})
                continue
            workspace = root / task_id
            shutil.copytree(fixture_root, workspace)
            if task_id == "long_horizon_001":
                materialize_long_horizon_corpus(workspace)
            evaluation = evaluate_artifacts(
                workspace,
                checks,
                fixture_root=fixture_root,
            )
            checked += 1
            if evaluation["passed"]:
                failures.append({
                    "task_id": task_id,
                    "reason": "untouched fixture passes grader",
                    "acceptance_score": evaluation["acceptance_score"],
                })
    return {
        "schema": "aios-bench/validation/v1",
        "ok": not failures,
        "checked_tasks": checked,
        "failures": failures,
    }


def _parametric_family(task: object) -> str:
    checks = [
        check for check in getattr(task, "acceptance", ())
        if check.get("type") == "parametric_reference"
    ]
    if len(checks) != 1:
        raise ValueError(f"task {getattr(task, 'id', 'unknown')} needs one parametric_reference")
    return str(checks[0]["family"])


def _write_oracle(run_dir: Path, task_id: str, oracle: Mapping[str, Any]) -> None:
    directory = run_dir / "oracles"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{task_id}.json").write_text(
        json.dumps(dict(oracle), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def validate_parametric_baseline(
    repo_root: Path,
    tasks: Iterable[object],
    *,
    base_seed: int,
    parameters: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate seeded generator determinism, variation and negative baseline."""
    failures: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    parameter_map = parameters or {}
    fixture_root = repo_root / "benchmarks" / "fixtures" / "workspace"

    with tempfile.TemporaryDirectory(prefix="aios-bench-v4-validate-") as temporary:
        root = Path(temporary)
        for task in tasks:
            task_id = str(getattr(task, "id"))
            checks = _checks(repo_root, task)
            family = _parametric_family(task)
            seed_a = derive_seed(base_seed, "task", task_id)
            seed_b = derive_seed(base_seed + 1, "task", task_id)
            pressure = parameter_map.get(family, {})

            work_a = root / task_id / "a"
            work_a2 = root / task_id / "a2"
            work_b = root / task_id / "b"
            oracle_a = materialize_variant(family, work_a, seed=seed_a, parameters=pressure)
            oracle_a2 = materialize_variant(family, work_a2, seed=seed_a, parameters=pressure)
            oracle_b = materialize_variant(family, work_b, seed=seed_b, parameters=pressure)

            deterministic = oracle_a.get("variant_digest") == oracle_a2.get("variant_digest")
            varies = oracle_a.get("variant_digest") != oracle_b.get("variant_digest")
            run_dir = root / task_id / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            _write_oracle(run_dir, task_id, oracle_a)
            evaluation = evaluate_artifacts(
                work_a,
                checks,
                run_dir=run_dir,
                fixture_root=fixture_root,
            )
            untouched_fails = not bool(evaluation["passed"])

            observation = {
                "task_id": task_id,
                "family": family,
                "seed": seed_a,
                "comparison_seed": seed_b,
                "variant_digest": oracle_a.get("variant_digest"),
                "comparison_variant_digest": oracle_b.get("variant_digest"),
                "same_seed_deterministic": deterministic,
                "different_seed_changes_variant": varies,
                "untouched_variant_fails": untouched_fails,
            }
            observations.append(observation)
            if not deterministic:
                failures.append({"task_id": task_id, "reason": "same seed produced different variants"})
            if not varies:
                failures.append({"task_id": task_id, "reason": "different seed did not change variant"})
            if not untouched_fails:
                failures.append({
                    "task_id": task_id,
                    "reason": "untouched generated variant passes grader",
                    "acceptance_score": evaluation["acceptance_score"],
                })

    return {
        "schema": "aios-bench/parametric-validation/v1",
        "ok": not failures,
        "checked_tasks": len(observations),
        "observations": observations,
        "failures": failures,
    }
