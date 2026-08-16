"""Shared base class for dimension scorers."""

from __future__ import annotations

from typing import ClassVar

from ghdtk.models.derived import DimensionId, DimensionScore, ScoreBreakdown
from ghdtk.scoring.framework import ScoreInputs, ScoringConfig


class BaseScorer:
    """Concrete scaffolding that implements the :class:`Scorer` protocol.

    Subclasses declare their ``dimension`` and ``label`` and implement
    :meth:`score`; the weight comes from the configured :class:`ScoringConfig`.
    """

    dimension: ClassVar[DimensionId]
    label: ClassVar[str]

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self.config = config or ScoringConfig()

    @property
    def weight(self) -> float:
        return self.config.weights.get(self.dimension, 1.0)

    def score(self, inputs: ScoreInputs) -> DimensionScore | None:
        """Score the dimension from the inputs, or ``None`` when unscorable."""
        raise NotImplementedError

    def _result(
        self,
        score: float,
        rationale: str,
        breakdown: list[ScoreBreakdown],
    ) -> DimensionScore:
        return DimensionScore(
            dimension=self.dimension,
            score=score,
            weight=self.weight,
            rationale=rationale,
            breakdown=breakdown,
        )
