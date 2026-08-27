from __future__ import annotations

from pathlib import Path

from core.benchmark.parametric.greenfield_registry import (
    GreenfieldRegistryPressure,
    evaluate_greenfield_registry_variant,
    generate_greenfield_registry_variant,
)
from core.benchmark.parametric_goldens import materialize_parametric_golden


def _variant(tmp_path: Path, seed: int = 121):
    workspace = tmp_path / "workspace"
    oracle = generate_greenfield_registry_variant(
        workspace,
        seed=seed,
        pressure=GreenfieldRegistryPressure(),
    )
    return workspace, oracle


def test_greenfield_baseline_has_no_implementation_and_fails(tmp_path: Path) -> None:
    workspace, oracle = _variant(tmp_path)

    result = evaluate_greenfield_registry_variant(workspace, oracle)

    assert result["passed"] is False
    assert "submitted tree missing" in result["detail"]


def test_greenfield_golden_passes_from_submitted_tree_only(tmp_path: Path) -> None:
    workspace, oracle = _variant(tmp_path)
    materialize_parametric_golden("greenfield_registry", workspace, oracle)

    result = evaluate_greenfield_registry_variant(workspace, oracle)

    assert result["passed"] is True, result["detail"]
    assert result["metrics"]["greenfield_verification_passed"] is True
    assert result["metrics"]["submitted_file_count"] == 2
    assert result["metrics"]["submitted_bytes"] > 0


def test_greenfield_files_outside_submission_cannot_satisfy_verifier(tmp_path: Path) -> None:
    workspace, oracle = _variant(tmp_path)
    fake = workspace / "registry_app"
    fake.mkdir()
    (fake / "__init__.py").write_text("class Registry: pass\n", encoding="utf-8")

    result = evaluate_greenfield_registry_variant(workspace, oracle)

    assert result["passed"] is False
    assert "submitted tree missing" in result["detail"]


def test_greenfield_specification_tampering_is_rejected(tmp_path: Path) -> None:
    workspace, oracle = _variant(tmp_path)
    materialize_parametric_golden("greenfield_registry", workspace, oracle)
    (workspace / "README.md").write_text("easier contract\n", encoding="utf-8")

    result = evaluate_greenfield_registry_variant(workspace, oracle)

    assert result["passed"] is False
    assert result["detail"] == "benchmark specification modified"


def test_greenfield_variant_changes_public_semantics_with_seed(tmp_path: Path) -> None:
    first_workspace, first = _variant(tmp_path / "a", seed=121)
    second_workspace, second = _variant(tmp_path / "b", seed=122)

    assert first["variant_digest"] != second["variant_digest"]
    assert first["max_name_length"] != second["max_name_length"]
    assert first_workspace.joinpath("README.md").read_text(encoding="utf-8") != second_workspace.joinpath("README.md").read_text(encoding="utf-8")
