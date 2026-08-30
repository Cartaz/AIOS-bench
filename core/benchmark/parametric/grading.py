from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class VariantGrade:
    """Deterministic result for one parametric family oracle.

    ``score`` is normalized to [0, 1] and supplies partial deterministic credit
    when a family has meaningful graded metrics. Existing binary families use
    ``binary`` so their behavior remains unchanged.
    """

    passed: bool
    detail: str
    score: float
    metrics: Mapping[str, Any] = field(default_factory=dict)
    failure_kind: str | None = None

    def __post_init__(self) -> None:
        score = float(self.score)
        if not 0.0 <= score <= 1.0:
            raise ValueError("variant grade score must be between 0 and 1")

    @classmethod
    def binary(
        cls,
        passed: bool,
        detail: str,
        *,
        failure_kind: str | None = None,
    ) -> "VariantGrade":
        return cls(
            passed=bool(passed),
            detail=str(detail),
            score=1.0 if passed else 0.0,
            failure_kind=failure_kind,
        )


__all__ = ["VariantGrade"]
