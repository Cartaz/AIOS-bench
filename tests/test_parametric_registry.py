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
    assert parameters["wide_retrieval"] == {
        "corpus_size": 96,
        "target_count": 12,
        "duplicate_records": 12,
        "conflict_records": 10,
        "source_depth": 3,
    }
    assert parameters["cross_artifact"] == {
        "row_count": 72,
        "group_count": 6,
        "excluded_rows": 12,
        "adjustment_rows": 8,
        "distractor_files": 3,
    }
    assert parameters["delegation_reconciliation"] == {
        "topic_count": 8,
        "conflict_count": 4,
        "distractor_records": 10,
        "fabricated_claims": 2,
    }
    assert parameters["epistemic_twins"] == {
        "pair_count": 6,
        "registry_size": 48,
        "distractor_records": 12,
        "archive_revisions": 3,
        "source_depth": 3,
    }
    assert parameters["black_box_reconstruction"] == {
        "rule_count": 7,
        "public_examples": 12,
        "probe_budget": 48,
        "distractor_fields": 3,
        "max_units": 500,
    }
    assert parameters["learning_transfer"] == {
        "demo_count": 3,
        "rows_per_demo": 54,
        "evaluation_rows": 60,
        "group_count": 6,
        "distractor_columns": 4,
        "schema_shift_fields": 4,
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
    assert parameters["wide_retrieval"]["target_count"] == 12
    assert parameters["cross_artifact"]["group_count"] == 6
    assert parameters["delegation_reconciliation"]["conflict_count"] == 4
    assert parameters["epistemic_twins"]["pair_count"] == 6
    assert parameters["black_box_reconstruction"]["probe_budget"] == 48
    assert parameters["learning_transfer"]["schema_shift_fields"] == 4


def test_parametric_registry_rejects_unknown_family() -> None:
    with pytest.raises(ValueError, match="unknown parametric families"):
        normalize_parameters({"not_a_family": {}})
