from __future__ import annotations

import hashlib
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

from .evaluators import evaluate_artifacts
from .experiments import derive_seed
from .materialization import ParametricTaskMaterializer
from .parametric import FAMILIES, materialize_variant, normalize_parameters
from .parametric_goldens import materialize_parametric_golden


HEALTH_SCHEMA = "aios-bench/benchmark-health/v1"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _write_oracle(run_dir: Path, task_id: str, oracle: Mapping[str, Any]) -> None:
    directory = run_dir / "oracles"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{task_id}.json").write_text(
        json.dumps(dict(oracle), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _protected_sources_intact(workspace: Path, oracle: Mapping[str, Any]) -> bool:
    protected = oracle.get("protected_sha256")
    if protected is None:
        return True
    if not isinstance(protected, Mapping):
        return False
    for relative, expected in protected.items():
        path = workspace / str(relative)
        if not path.is_file():
            return False
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != str(expected):
            return False
    return True


def _task_contract(task: object, family: str) -> tuple[bool, list[str]]:
    issues: list[str] = []
    task_id = str(getattr(task, "id", ""))
    prompt = str(getattr(task, "prompt", ""))
    checks = list(getattr(task, "acceptance", ()) or ())
    authoritative = [item for item in checks if item.get("type") == "parametric_reference"]
    if len(authoritative) != 1:
        issues.append("expected exactly one parametric_reference check")
    elif authoritative[0].get("family") != family:
        issues.append("task family and authoritative grader family differ")
    elif authoritative[0].get("task_id") != task_id:
        issues.append("authoritative grader task_id differs from catalog task id")
    for check in checks:
        if check.get("type") == "exists":
            path = str(check.get("path", ""))
            if path and path not in prompt:
                issues.append(f"required artifact is not named in prompt: {path}")
    return not issues, issues


def _schema_ok(oracle: Mapping[str, Any], family: str) -> bool:
    digest = oracle.get("variant_digest")
    parameters = oracle.get("parameters")
    return bool(
        oracle.get("family") == family
        and isinstance(parameters, Mapping)
        and isinstance(digest, str)
        and _DIGEST.fullmatch(digest)
    )


def _workspace_hides_oracle(workspace: Path, oracle: Mapping[str, Any]) -> bool:
    """Check structural separation without guessing family-specific secret names."""
    if (workspace / "oracles").exists():
        return False
    digest = str(oracle.get("variant_digest", ""))
    if digest:
        for path in workspace.rglob("*"):
            if path.is_file():
                try:
                    if digest in path.read_text(encoding="utf-8", errors="ignore"):
                        return False
                except OSError:
                    return False
    return True


def _remove_required_artifact(workspace: Path, task: object) -> str | None:
    for check in getattr(task, "acceptance", ()) or ():
        if check.get("type") != "exists":
            continue
        relative = str(check.get("path", ""))
        path = workspace / relative
        if path.is_file():
            path.unlink()
            return relative
    return None


def validate_benchmark_health(
    repo_root: Path,
    tasks: Iterable[object],
    *,
    base_seed: int = 42,
    parameters: Mapping[str, Mapping[str, Any]] | None = None,
    max_grader_seconds: float = 30.0,
) -> dict[str, Any]:
    """Validate benchmark construction independently of agent performance.

    The health gate checks deterministic generation, seed diversity, complete
    task/grader contracts, hidden-oracle separation, source integrity, positive
    and negative satisfiability, a missing-required-artifact near miss, and a
    second-seed golden witness. It never invokes an LLM or harness.
    """
    if max_grader_seconds <= 0:
        raise ValueError("max_grader_seconds must be greater than 0")
    parameter_map = normalize_parameters(parameters)
    observations: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="aios-bench-health-") as temporary:
        root = Path(temporary)
        for task in tasks:
            task_id = str(getattr(task, "id"))
            try:
                family = ParametricTaskMaterializer.family(task)  # type: ignore[arg-type]
            except ValueError as exc:
                failures.append({"task_id": task_id, "reason": str(exc)})
                continue
            if family not in FAMILIES:
                failures.append({"task_id": task_id, "reason": f"unknown family: {family}"})
                continue

            seed_a = derive_seed(base_seed, "task", task_id)
            seed_b = derive_seed(base_seed + 1, "task", task_id)
            pressure = parameter_map[family]
            work_a = root / task_id / "a"
            work_a2 = root / task_id / "a2"
            work_b = root / task_id / "b"
            oracle_a = materialize_variant(family, work_a, seed=seed_a, parameters=pressure)
            oracle_a2 = materialize_variant(family, work_a2, seed=seed_a, parameters=pressure)
            oracle_b = materialize_variant(family, work_b, seed=seed_b, parameters=pressure)

            same_seed_oracle = oracle_a.get("variant_digest") == oracle_a2.get("variant_digest")
            same_seed_workspace = _tree_digest(work_a) == _tree_digest(work_a2)
            different_seed_oracle = oracle_a.get("variant_digest") != oracle_b.get("variant_digest")
            different_seed_workspace = _tree_digest(work_a) != _tree_digest(work_b)
            schema_ok = _schema_ok(oracle_a, family)
            sources_intact = _protected_sources_intact(work_a, oracle_a)
            oracle_hidden = _workspace_hides_oracle(work_a, oracle_a)
            contract_ok, contract_issues = _task_contract(task, family)

            checks = list(getattr(task, "acceptance", ()) or ())
            fixture_root = repo_root / "benchmarks" / "fixtures" / "workspace"
            run_a = root / task_id / "run-a"
            _write_oracle(run_a, task_id, oracle_a)
            untouched = evaluate_artifacts(
                work_a,
                checks,
                run_dir=run_a,
                fixture_root=fixture_root,
            )
            untouched_fails = not bool(untouched["passed"])

            golden_a = root / task_id / "golden-a"
            oracle_golden_a = materialize_variant(
                family,
                golden_a,
                seed=seed_a,
                parameters=pressure,
            )
            golden_run_a = root / task_id / "golden-run-a"
            _write_oracle(golden_run_a, task_id, oracle_golden_a)
            materialize_parametric_golden(
                family,
                golden_a,
                oracle_golden_a,
                run_dir=golden_run_a,
                task_id=task_id,
            )
            started = time.monotonic()
            positive_a = evaluate_artifacts(
                golden_a,
                checks,
                run_dir=golden_run_a,
                fixture_root=fixture_root,
            )
            grader_seconds = time.monotonic() - started
            golden_passes = bool(positive_a["passed"])
            grader_within_budget = grader_seconds <= max_grader_seconds

            removed = _remove_required_artifact(golden_a, task)
            if removed is None:
                missing_artifact_fails = False
            else:
                near_miss = evaluate_artifacts(
                    golden_a,
                    checks,
                    run_dir=golden_run_a,
                    fixture_root=fixture_root,
                )
                missing_artifact_fails = not bool(near_miss["passed"])

            golden_b = root / task_id / "golden-b"
            oracle_golden_b = materialize_variant(
                family,
                golden_b,
                seed=seed_b,
                parameters=pressure,
            )
            golden_run_b = root / task_id / "golden-run-b"
            _write_oracle(golden_run_b, task_id, oracle_golden_b)
            materialize_parametric_golden(
                family,
                golden_b,
                oracle_golden_b,
                run_dir=golden_run_b,
                task_id=task_id,
            )
            comparison_positive = evaluate_artifacts(
                golden_b,
                checks,
                run_dir=golden_run_b,
                fixture_root=fixture_root,
            )
            comparison_golden_passes = bool(comparison_positive["passed"])

            observation = {
                "task_id": task_id,
                "family": family,
                "same_seed_oracle_deterministic": same_seed_oracle,
                "same_seed_workspace_deterministic": same_seed_workspace,
                "different_seed_changes_oracle": different_seed_oracle,
                "different_seed_changes_workspace": different_seed_workspace,
                "oracle_schema_valid": schema_ok,
                "oracle_hidden_from_workspace": oracle_hidden,
                "protected_sources_intact": sources_intact,
                "task_contract_consistent": contract_ok,
                "contract_issues": contract_issues,
                "untouched_variant_fails": untouched_fails,
                "golden_variant_passes": golden_passes,
                "comparison_seed_golden_passes": comparison_golden_passes,
                "missing_required_artifact": removed,
                "missing_required_artifact_fails": missing_artifact_fails,
                "grader_seconds": grader_seconds,
                "grader_within_budget": grader_within_budget,
            }
            observations.append(observation)

            checks_by_name = {
                "same seed oracle is nondeterministic": same_seed_oracle,
                "same seed workspace is nondeterministic": same_seed_workspace,
                "different seed does not change oracle": different_seed_oracle,
                "different seed does not change workspace": different_seed_workspace,
                "oracle schema is invalid": schema_ok,
                "oracle identity leaks into workspace": oracle_hidden,
                "protected source integrity failed at materialization": sources_intact,
                "task instructions and verifier contract disagree": contract_ok,
                "untouched generated variant passes grader": untouched_fails,
                "benchmark-owned golden variant fails grader": golden_passes,
                "comparison-seed golden variant fails grader": comparison_golden_passes,
                "missing required artifact does not fail grader": missing_artifact_fails,
                "grader exceeded health runtime budget": grader_within_budget,
            }
            for reason, passed in checks_by_name.items():
                if not passed:
                    failure: dict[str, Any] = {"task_id": task_id, "reason": reason}
                    if reason == "task instructions and verifier contract disagree":
                        failure["issues"] = contract_issues
                    if reason == "grader exceeded health runtime budget":
                        failure.update({
                            "grader_seconds": grader_seconds,
                            "max_grader_seconds": max_grader_seconds,
                        })
                    failures.append(failure)

    return {
        "schema": HEALTH_SCHEMA,
        "ok": not failures,
        "base_seed": int(base_seed),
        "max_grader_seconds": float(max_grader_seconds),
        "pressure_coordinates": parameter_map,
        "checked_tasks": len(observations),
        "observations": observations,
        "failures": failures,
    }


__all__ = ["HEALTH_SCHEMA", "validate_benchmark_health"]
