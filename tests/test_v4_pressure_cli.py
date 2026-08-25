from types import SimpleNamespace

import pytest

from aios_bench import cli


def _args(**overrides):
    values = {
        "v4_expense_rows": 48,
        "v4_expense_malformed": 2,
        "v4_expense_distractors": 3,
        "v4_expense_months": 6,
        "v4_config_chain_depth": 3,
        "v4_config_distractors": 3,
        "v4_config_extra_settings": 2,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_v4_parameters_include_every_active_family():
    parameters = cli._v4_parameters(_args())

    assert parameters == {
        "expense_report": {
            "rows": 48,
            "malformed_rows": 2,
            "distractor_files": 3,
            "months": 6,
        },
        "config_traversal": {
            "chain_depth": 3,
            "distractor_files": 3,
            "extra_settings": 2,
        },
    }


def test_v4_config_pressure_is_configurable():
    parameters = cli._v4_parameters(
        _args(v4_config_chain_depth=6, v4_config_distractors=10, v4_config_extra_settings=5)
    )

    assert parameters["config_traversal"] == {
        "chain_depth": 6,
        "distractor_files": 10,
        "extra_settings": 5,
    }


def test_v4_config_pressure_rejects_invalid_coordinates():
    with pytest.raises(SystemExit, match="invalid Frontier v4 config pressure"):
        cli._v4_parameters(_args(v4_config_chain_depth=1))
