from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP

from .models import Trajectory


SCORING_SCHEMA = "aios-bench/scoring/v2"


def score_trajectory(t: Trajectory) -> dict[str, float]:
    """Return normalized deterministic quality plus diagnostic execution metrics.

    ``acceptance`` is the only input to the public 0-100 task score. The other
    metrics remain useful diagnostics, but they must not change correctness or
    create harness-dependent leaderboard credit.
    """
    acceptance = 0.0 if t.evaluation_score is None else float(t.evaluation_score)
    execution = 1.0 if t.success else 0.0
    recovery = (
        1.0
        if t.errors == 0
        else max(
            0.0,
            1.0
            - (t.errors - min(t.retries, t.errors)) / max(t.errors, 1),
        )
    )
    intervention = 1.0 / (1.0 + t.human_interventions)
    proportionality = 1.0 / (1.0 + max(0, t.tool_calls - 8) * 0.04)
    return {
        "acceptance": acceptance,
        "execution": execution,
        "error_recovery": recovery,
        "human_independence": intervention,
        "proportionality": proportionality,
    }


def acceptance_points(value: float | None) -> int:
    """Quantize normalized deterministic acceptance to an integer 0-100 score.

    Every integer point is representable: an acceptance value of ``n / 100``
    maps exactly to ``n``. Decimal half-up rounding avoids Python's banker
    rounding at x.5 boundaries and makes the published scale intuitive.
    """
    if value is None:
        return 0
    score = float(value)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError("acceptance score must be finite and between 0 and 1")
    points = (Decimal(str(score)) * Decimal(100)).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return int(points)


def overall_score(t: Trajectory) -> int:
    """Return deterministic artifact quality on the public integer 0-100 scale.

    Execution outcome is deliberately orthogonal. PASS/WRONG/TIMEOUT/etc. are
    reported by the runner's status/failure taxonomy; a high-quality artifact
    is not silently compressed merely because the process failed to terminate.
    Infrastructure/non-comparable failures are still excluded by the runner and
    retain ``score=None`` before this function is called.
    """
    return acceptance_points(t.evaluation_score)


__all__ = [
    "SCORING_SCHEMA",
    "acceptance_points",
    "overall_score",
    "score_trajectory",
]
