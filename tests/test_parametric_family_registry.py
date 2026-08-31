from core.benchmark.parametric import (
    FAMILIES,
    FAMILY_SPECS,
    ParametricFamilySpec,
    diagnose_variant_failure,
    evaluate_variant,
    start_variant_runtime,
)


def test_family_registry_is_single_source_for_all_parametric_families() -> None:
    assert set(FAMILY_SPECS) == FAMILIES
    assert all(isinstance(spec, ParametricFamilySpec) for spec in FAMILY_SPECS.values())
    assert all(spec.pressure_type is not None for spec in FAMILY_SPECS.values())
    assert all(callable(spec.generator) and callable(spec.grader) for spec in FAMILY_SPECS.values())


def test_runtime_ownership_is_explicit_in_family_registry() -> None:
    runtime_families = {
        family for family, spec in FAMILY_SPECS.items() if spec.runtime is not None
    }
    assert runtime_families == {
        "stateful_world",
        "dependency_world",
        "tool_recovery",
        "black_box_reconstruction",
    }


def test_unknown_family_public_dispatch_compatibility(tmp_path) -> None:
    runtime = start_variant_runtime(
        "unknown",
        tmp_path,
        run_dir=tmp_path / "run",
        task_id="task",
        oracle={},
    )
    try:
        assert runtime.environment == {}
    finally:
        runtime.close()

    grade = evaluate_variant("unknown", tmp_path, {})
    assert grade.passed is False
    assert grade.score == 0.0
    assert "unknown parametric family" in grade.detail
    assert diagnose_variant_failure("unknown", {}) is None
