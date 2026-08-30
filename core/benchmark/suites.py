from __future__ import annotations

from typing import Any, Mapping

from .frontier_runner import SuiteDefinition
from .materialization import ParametricTaskMaterializer, StaticTaskMaterializer
from .parametric import normalize_parameters


def frontier_v3_suite() -> SuiteDefinition:
    return SuiteDefinition(
        name="frontier_v3",
        catalog_dir="frontier_v3",
        materializer=StaticTaskMaterializer(),
        fixture_dirs=("benchmarks/fixtures",),
    )


def frontier_v4_suite(
    *,
    variant_base_seed: int = 42,
    parametric_parameters: Mapping[str, Mapping[str, Any]] | None = None,
) -> SuiteDefinition:
    parameters = normalize_parameters(parametric_parameters)
    return SuiteDefinition(
        name="frontier_v4",
        catalog_dir="frontier_v4",
        materializer=ParametricTaskMaterializer(
            base_seed=int(variant_base_seed),
            parameters=parameters,
        ),
        parametric={
            "schema": "aios-bench/parametric/v1",
            "suite": "frontier_v4",
            "pressure_coordinates": parameters,
            "seeded_variants": True,
        },
    )


SUITE_NAMES = ("frontier_v3", "frontier_v4")
