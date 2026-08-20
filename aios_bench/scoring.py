from __future__ import annotations

from .models import Trajectory


def score_trajectory(t: Trajectory) -> dict[str, float]:
    # Artifact acceptance is deliberately the dominant signal. A zero-exit
    # process is not a successful task if the requested deliverable is wrong.
    acceptance = 0.0 if t.evaluation_score is None else t.evaluation_score
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
    # Only deterministic acceptance and successful execution are comparable
    # across harnesses. Telemetry-derived efficiency metrics remain available
    # for diagnostics, but missing telemetry cannot inflate the leaderboard.
    raw = 100.0 * (0.80 * s["acceptance"] + 0.20 * s["execution"])
    return raw if t.success else min(raw, 49.0)
