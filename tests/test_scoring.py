from aios_bench.models import Trajectory
from aios_bench.scoring import overall_score


def test_missing_evaluation_never_receives_free_acceptance_credit():
    trajectory = Trajectory("agent", "task", success=True, evaluation_score=None)
    assert overall_score(trajectory) == 20.0


def test_failed_task_is_capped_below_passing_range():
    trajectory = Trajectory("agent", "task", success=False, evaluation_score=1.0)
    assert overall_score(trajectory) == 49.0


def test_successful_deterministic_evaluation_is_full_score():
    trajectory = Trajectory("agent", "task", success=True, evaluation_score=1.0)
    assert overall_score(trajectory) == 100.0
