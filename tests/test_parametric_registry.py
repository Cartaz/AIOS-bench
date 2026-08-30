from __future__ import annotations

import pytest

from aios_bench.parametric import FAMILIES, normalize_parameters


def test_parametric_registry_records_defaults_for_every_family() -> None:
    parameters = normalize_parameters()

    assert set(parameters) == FAMILIES
    assert parameters["workspace_lineage"] == {
        "lineage_depth": 4,
        "branch_count": 3,
        "stale_revisions": 2,
        "distractor_files": 4,
        "extra_settings": 2,
    }


def test_parametric_registry_merges_partial_overrides_with_other_defaults() -> None:
    parameters = normalize_parameters({
        "workspace_lineage": {
            "lineage_depth": 6,
            "branch_count": 5,
            "stale_revisions": 4,
            "distractor_files": 8,
            "extra_settings": 5,
        }
    })

    assert parameters["workspace_lineage"]["lineage_depth"] == 6
    assert parameters["expense_report"] == {
        "rows": 48,
        "malformed_rows": 2,
        "distractor_files": 3,
        "months": 6,
    }


def test_parametric_registry_rejects_unknown_family() -> None:
    with pytest.raises(ValueError, match="unknown parametric families"):
        normalize_parameters({"not_a_family": {}})
