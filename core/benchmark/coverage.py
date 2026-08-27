from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class CoverageMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    completion: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


def evaluate_set_coverage(
    required: Iterable[str],
    observed_positive: Iterable[str],
) -> CoverageMetrics:
    """Evaluate exact finite-set coverage without changing capability semantics."""
    required_set = frozenset(str(item) for item in required)
    observed_set = frozenset(str(item) for item in observed_positive)
    true_positives = len(required_set & observed_set)
    false_positives = len(observed_set - required_set)
    false_negatives = len(required_set - observed_set)
    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 1.0 if not required_set else 0.0
    )
    recall = true_positives / len(required_set) if required_set else 1.0
    completion = 1.0 if false_positives == 0 and false_negatives == 0 else recall
    return CoverageMetrics(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        completion=completion,
    )


__all__ = ["CoverageMetrics", "evaluate_set_coverage"]
