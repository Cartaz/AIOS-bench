import pytest

from aios_bench.models import Trajectory
from aios_bench.scoring import SCORING_SCHEMA, acceptance_points, overall_score


def test_missing_evaluation_receives_zero_deterministic_credit():
    trajectory = Trajectory("agent", "task", success=True, evaluation_score=None)
    assert overall_score(trajectory) == 0


def test_execution_failure_does_not_cap_deterministic_quality():
    trajectory = Trajectory("agent", "task", success=False, evaluation_score=1.0)
    assert overall_score(trajectory) == 100


def test_successful_deterministic_evaluation_is_full_score():
    trajectory = Trajectory("agent", "task", success=True, evaluation_score=1.0)
    assert overall_score(trajectory) == 100


def test_every_integer_point_from_zero_to_one_hundred_is_representable():
    observed = {
        overall_score(
            Trajectory(
                "agent",
                f"task-{points}",
                success=points == 100,
                evaluation_score=points / 100,
            )
        )
        for points in range(101)
    }
    assert observed == set(range(101))


def test_public_quantization_uses_half_up_rounding():
    assert acceptance_points(0.0049) == 0
    assert acceptance_points(0.005) == 1
    assert acceptance_points(0.9949) == 99
    assert acceptance_points(0.995) == 100


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
def test_invalid_acceptance_values_are_rejected(value):
    with pytest.raises(ValueError, match="between 0 and 1"):
        acceptance_points(value)


def test_scoring_semantics_are_explicitly_versioned():
    assert SCORING_SCHEMA == "aios-bench/scoring/v2"
