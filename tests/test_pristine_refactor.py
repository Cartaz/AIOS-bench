from __future__ import annotations

from pathlib import Path

from core.benchmark.parametric.pristine_refactor import (
    PristineRefactorPressure,
    evaluate_pristine_refactor_variant,
    generate_pristine_refactor_variant,
)
from core.benchmark.parametric_goldens import materialize_parametric_golden


def _variant(tmp_path: Path, seed: int = 121):
    workspace = tmp_path / "workspace"
    oracle = generate_pristine_refactor_variant(
        workspace,
        seed=seed,
        pressure=PristineRefactorPressure(),
    )
    return workspace, oracle


def test_pristine_refactor_baseline_fails_hidden_priority_integration(tmp_path: Path) -> None:
    workspace, oracle = _variant(tmp_path)

    result = evaluate_pristine_refactor_variant(workspace, oracle)

    assert result["passed"] is False
    assert result["metrics"]["pristine_verification_passed"] is False
    assert result["metrics"]["changed_artifact_count"] == 0


def test_pristine_refactor_golden_passes_from_reconstructed_artifact(tmp_path: Path) -> None:
    workspace, oracle = _variant(tmp_path)
    materialize_parametric_golden("pristine_refactor", workspace, oracle)

    result = evaluate_pristine_refactor_variant(workspace, oracle)

    assert result["passed"] is True, result["detail"]
    assert result["metrics"]["pristine_verification_passed"] is True
    assert result["metrics"]["changed_artifact_count"] == 4
    assert {item["path"] for item in result["metrics"]["changed_artifacts"]} == set(oracle["artifact_paths"])


def test_workspace_local_test_tampering_cannot_make_pristine_verification_pass(tmp_path: Path) -> None:
    workspace, oracle = _variant(tmp_path)
    public_test = workspace / "tests" / "test_public.py"
    public_test.write_text("# fake green local test\n", encoding="utf-8")

    result = evaluate_pristine_refactor_variant(workspace, oracle)

    assert result["passed"] is False
    assert "protected file modified" in result["detail"]


def test_high_level_service_shortcut_is_rejected_before_hidden_verification(tmp_path: Path) -> None:
    workspace, oracle = _variant(tmp_path)
    service = workspace / "order_service" / "service.py"
    service.write_text(
        service.read_text(encoding="utf-8") + "\n# local shortcut attempt\n",
        encoding="utf-8",
    )

    result = evaluate_pristine_refactor_variant(workspace, oracle)

    assert result["passed"] is False
    assert "order_service/service.py" in result["detail"]


def test_pristine_variant_changes_semantically_with_seed(tmp_path: Path) -> None:
    _, first = _variant(tmp_path / "a", seed=121)
    _, second = _variant(tmp_path / "b", seed=122)

    assert first["variant_digest"] != second["variant_digest"]
    assert (
        first["express_surcharge"],
        first["priority_surcharge"],
        first["priority_queue"],
        first["priority_code"],
    ) != (
        second["express_surcharge"],
        second["priority_surcharge"],
        second["priority_queue"],
        second["priority_code"],
    )
