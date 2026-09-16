"""Contract tests for the seeded software-repair migration family."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from core.benchmark.parametric import evaluate_variant, materialize_variant
from core.benchmark.parametric.software_repair import SoftwareRepairPressure
from core.benchmark.parametric_goldens import materialize_parametric_golden


def _snapshot(workspace: Path) -> dict[str, bytes]:
    return {p.relative_to(workspace).as_posix(): p.read_bytes()
            for p in sorted(workspace.rglob("*")) if p.is_file()}


def test_pressure_rejects_invalid_and_unknown_coordinates() -> None:
    with pytest.raises(ValueError, match="hidden_cases"):
        SoftwareRepairPressure(hidden_cases=5)
    with pytest.raises(ValueError, match="unknown software repair"):
        SoftwareRepairPressure.from_mapping({"hidden_cases": 96, "unknown": 1})


def test_seed_reproducibility_and_pressure_identity(tmp_path: Path) -> None:
    a, b, c = (tmp_path / name for name in ("a", "b", "c"))
    first = materialize_variant("software_repair", a, seed=42)
    second = materialize_variant("software_repair", b, seed=42)
    third = materialize_variant("software_repair", c, seed=43)
    assert first["variant_digest"] == second["variant_digest"]
    assert _snapshot(a) == _snapshot(b)
    assert first["variant_digest"] != third["variant_digest"]
    assert not (a / "oracles").exists()
    assert first["variant_digest"] not in "\n".join(
        path.read_text(encoding="utf-8") for path in a.rglob("*") if path.is_file())


def test_original_is_buggy_and_golden_repairs_public_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("software_repair", workspace, seed=7)
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
    before = subprocess.run(command, cwd=workspace, text=True, capture_output=True,
                            check=False, timeout=12)
    assert before.returncode != 0
    materialize_parametric_golden("software_repair", workspace, oracle)
    after = subprocess.run(command, cwd=workspace, text=True, capture_output=True,
                           check=False, timeout=12)
    assert after.returncode == 0, after.stderr
    assert (workspace / "tests/test_regression.py").is_file()
    assert json.loads((workspace / "reports/repair.json").read_text())["diagnoses"]


def test_protected_source_tampering_fails_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("software_repair", workspace, seed=10)
    materialize_parametric_golden("software_repair", workspace, oracle)
    protected = workspace / "docs/contract.md"
    protected.write_text(protected.read_text() + "tampered", encoding="utf-8")
    grade = evaluate_variant("software_repair", workspace, oracle)
    assert not grade.passed
    assert "protected source modified" in grade.detail


def test_sandboxed_golden_and_missing_regression(tmp_path: Path) -> None:
    if shutil.which("bwrap") is None:
        pytest.skip("Bubblewrap is necessary to execute untrusted task code")
    workspace = tmp_path / "workspace"
    oracle = materialize_variant("software_repair", workspace, seed=11)
    materialize_parametric_golden("software_repair", workspace, oracle)
    grade = evaluate_variant("software_repair", workspace, oracle)
    assert grade.passed, grade.detail
    assert grade.score == 1.0
    assert grade.metrics["hidden_sandboxed"] is True
    assert grade.metrics["regression_mutation_detected"] is True
    (workspace / "tests/test_regression.py").write_text("# no regression assertions\n", encoding="utf-8")
    no_op = evaluate_variant("software_repair", workspace, oracle)
    assert not no_op.passed
    assert no_op.metrics["regression_mutation_detected"] is False
    (workspace / "tests/test_regression.py").unlink()
    rejected = evaluate_variant("software_repair", workspace, oracle)
    assert not rejected.passed
