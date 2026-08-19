from __future__ import annotations

from .models import Trajectory


def score_trajectory(t: Trajectory) -> dict[str, float]:
    success = 1.0 if t.success else 0.0
    recovery = 1.0 if t.errors == 0 else max(0.0, 1.0 - (t.errors - min(t.retries, t.errors)) / max(t.errors, 1))
    intervention = 1.0 / (1.0 + t.human_interventions)
    proportionality = 1.0 / (1.0 + max(0, t.tool_calls - 5) * 0.05)
    return {
        "success": success,
        "error_recovery": recovery,
        "human_independence": intervention,
        "proportionality": proportionality,
    }


def overall_score(t: Trajectory) -> float:
    s = score_trajectory(t)
    return 100.0 * (
        0.55 * s["success"]
        + 0.15 * s["error_recovery"]
        + 0.15 * s["human_independence"]
        + 0.15 * s["proportionality"]
    )
