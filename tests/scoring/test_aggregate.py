"""Tests for the overall score aggregation (issue #50)."""

from __future__ import annotations

import pytest

from ghdtk.models.derived import DimensionId, DimensionScore
from ghdtk.scoring import ScoringConfig
from ghdtk.scoring.aggregate import aggregate_dimension_scores


def _score(
    dimension: DimensionId,
    value: float,
    weight: float = 1.0,
) -> DimensionScore:
    return DimensionScore(dimension=dimension, score=value, weight=weight)


def test_weighted_average_and_contributions() -> None:
    scores = [
        _score(DimensionId.PRESENCE, 80.0, weight=1.0),
        _score(DimensionId.ACTIVITY, 60.0, weight=1.5),
    ]
    overall = aggregate_dimension_scores(scores)
    assert overall is not None
    assert overall.overall == 68.0
    by_dimension = {item.dimension: item for item in overall.contributions}
    assert by_dimension[DimensionId.PRESENCE].contribution == 32.0
    assert by_dimension[DimensionId.ACTIVITY].contribution == 36.0
    assert sum(item.contribution for item in overall.contributions) == pytest.approx(68.0)
    assert overall.strengths == ["Profile presence (80/100)"]
    assert overall.weaknesses == []


def test_all_equal_scores_share_contributions() -> None:
    scores = [
        _score(DimensionId.PRESENCE, 50.0),
        _score(DimensionId.ACTIVITY, 50.0),
        _score(DimensionId.CONSISTENCY, 50.0),
    ]
    overall = aggregate_dimension_scores(scores)
    assert overall is not None
    assert overall.overall == 50.0
    assert len(overall.contributions) == 3
    assert [item.contribution for item in overall.contributions] == pytest.approx([50.0 / 3] * 3)
    assert overall.strengths == []
    assert overall.weaknesses == []


def test_single_missing_dimension_renormalizes() -> None:
    overall = aggregate_dimension_scores([_score(DimensionId.PRESENCE, 42.0)])
    assert overall is not None
    assert overall.overall == 42.0
    assert overall.contributions[0].contribution == 42.0


def test_zero_weight_dimension_is_excluded() -> None:
    scores = [
        _score(DimensionId.PRESENCE, 80.0, weight=0.0),
        _score(DimensionId.ACTIVITY, 60.0),
    ]
    overall = aggregate_dimension_scores(scores)
    assert overall is not None
    assert overall.overall == 60.0
    assert [item.dimension for item in overall.contributions] == [DimensionId.ACTIVITY]


def test_empty_scores_produce_no_overall() -> None:
    assert aggregate_dimension_scores([]) is None
    all_zero = [_score(DimensionId.PRESENCE, 80.0, weight=0.0)]
    assert aggregate_dimension_scores(all_zero) is None


def test_strengths_and_weaknesses_derived_deterministically() -> None:
    scores = [
        _score(DimensionId.PRESENCE, 90.0),
        _score(DimensionId.CODE_QUALITY, 75.0),
        _score(DimensionId.ACTIVITY, 20.0),
        _score(DimensionId.CONSISTENCY, 10.0),
    ]
    overall = aggregate_dimension_scores(scores)
    assert overall is not None
    assert overall.strengths == [
        "Profile presence (90/100)",
        "Code quality (75/100)",
    ]
    assert overall.weaknesses == [
        "Consistency (10/100)",
        "Activity (20/100)",
    ]


def test_strength_limit_and_custom_thresholds() -> None:
    scores = [
        _score(DimensionId.PRESENCE, 90.0),
        _score(DimensionId.CODE_QUALITY, 80.0),
        _score(DimensionId.ACTIVITY, 70.0),
        _score(DimensionId.OPEN_SOURCE, 60.0),
    ]
    config = ScoringConfig(
        strength_threshold=50.0,
        weakness_threshold=65.0,
        max_strengths=2,
        max_weaknesses=1,
    )
    overall = aggregate_dimension_scores(scores, config)
    assert overall is not None
    assert overall.strengths == [
        "Profile presence (90/100)",
        "Code quality (80/100)",
    ]
    assert overall.weaknesses == ["Open source (60/100)"]


def test_configured_weights_change_the_overall() -> None:
    scores = [
        _score(DimensionId.PRESENCE, 80.0, weight=3.0),
        _score(DimensionId.ACTIVITY, 60.0, weight=1.0),
    ]
    overall = aggregate_dimension_scores(scores)
    assert overall is not None
    assert overall.overall == 75.0
