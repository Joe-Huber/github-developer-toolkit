"""Overall score aggregation and explainability (issue #50).

Combines dimension scores into a weighted overall profile score with a
transparent breakdown. Each dimension's contribution is its score scaled by its
weight over the total active weight, so the contributions sum to the overall
score. Strengths and weaknesses are derived deterministically from the
dimension scores and the configured thresholds.
"""

from __future__ import annotations

from collections.abc import Sequence

from ghdtk.models.derived import (
    DimensionContribution,
    DimensionScore,
    OverallScore,
)
from ghdtk.scoring.framework import ScoringConfig, dimension_label


def aggregate_dimension_scores(
    scores: Sequence[DimensionScore],
    config: ScoringConfig | None = None,
) -> OverallScore | None:
    """Aggregate dimension scores into an overall score, or ``None``.

    Dimensions with zero weight are excluded from the aggregation. With no
    scored dimensions at all the overall score is ``None`` (nothing to
    aggregate); otherwise missing dimensions are simply skipped and the
    remaining weights are re-normalized.
    """
    config = config or ScoringConfig()
    scored = [score for score in scores if score.weight > 0]
    if not scored:
        return None
    total_weight = sum(score.weight for score in scored)
    if total_weight <= 0:
        return None

    overall = sum(score.score * score.weight for score in scored) / total_weight
    contributions = [
        DimensionContribution(
            dimension=score.dimension,
            score=score.score,
            weight=score.weight,
            contribution=score.score * score.weight / total_weight,
        )
        for score in scored
    ]
    strengths = _top_dimensions(
        scored,
        at_or_above=config.strength_threshold,
        limit=config.max_strengths,
        weakest_first=False,
    )
    weaknesses = _top_dimensions(
        scored,
        at_or_above=config.weakness_threshold,
        limit=config.max_weaknesses,
        weakest_first=True,
    )
    return OverallScore(
        overall=overall,
        contributions=contributions,
        strengths=strengths,
        weaknesses=weaknesses,
    )


def _top_dimensions(
    scores: Sequence[DimensionScore],
    *,
    at_or_above: float,
    limit: int,
    weakest_first: bool,
) -> list[str]:
    """Rank dimensions against a threshold and format the top ``limit``.

    Strengths are dimensions at or above the strength threshold ranked best
    first; weaknesses are dimensions at or below the weakness threshold ranked
    worst first. Ties break on the dimension id so the output is deterministic.
    """
    if weakest_first:
        filtered = [score for score in scores if score.score <= at_or_above]
        ordered = sorted(filtered, key=lambda s: (s.score, s.dimension.value))
    else:
        filtered = [score for score in scores if score.score >= at_or_above]
        ordered = sorted(filtered, key=lambda s: (-s.score, s.dimension.value))
    return [
        f"{dimension_label(score.dimension)} ({score.score:.0f}/100)" for score in ordered[:limit]
    ]
