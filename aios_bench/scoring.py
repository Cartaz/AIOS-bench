from __future__ import annotations

from .models import Trajectory


def score_trajectory(t: Trajectory) -> dict[str, float]:
    # Artifact acceptance is deliberately the dominant signal. A zero-exit
    # process is not a successful task if the requested deliverable is wrong.
    acceptance = 1.0 if t.evaluation_score is None else t.evaluation_score
    execution = 1.0 if t.success else 0.0
    recovery = 1.0 if t.errors == 0 else max(0.0, 1.0 - (t.errors - min(t.retries, t.errors)) / max(t.errors, 1))
    intervention = 1.0 / (1.0 + t.human_interventions)
    proportionality = 1.0 / (1.0 + max(0, t.tool_calls - 8) * 0.04)
    return {
        "acceptance": acceptance,
        "execution": execution,
        "error_recovery": recovery,
        "human_independence": intervention,
        "proportionality": proportionality,
    }


def overall_score(t: Trajectory) -> float:
    s = score_trajectory(t)
    return 100.0 * (
        0.60 * s["acceptance"]
        + 0.15 * s["execution"]
        + 0.10 * s["error_recovery"]
        + 0.10 * s["human_independence"]
        + 0.05 * s["proportionality"]
    )
