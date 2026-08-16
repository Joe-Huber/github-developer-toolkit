"""Tests for the visibility dimension scorer (issue #49)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ghdtk.analyzers.languages import LanguageDistributionAnalysis
from ghdtk.analyzers.stars import StarsAnalysis, StarsRankingEntry
from ghdtk.models.derived import DimensionId, MetricRecord
from ghdtk.scoring import ScoreInputs
from ghdtk.scoring.scorers.visibility import VisibilityScorer

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _metric(metric_id: str, value: object) -> MetricRecord:
    return MetricRecord(
        id=metric_id,
        label=metric_id,
        value=value,
        sources=[],
        timestamp=NOW,
    )


def _stars(
    total: int | None = None,
    ranking: list[StarsRankingEntry] | None = None,
) -> StarsAnalysis:
    metrics = []
    if total is not None:
        metrics.append(_metric("portfolio.stars.total", total))
    return StarsAnalysis(
        username="octocat",
        ranking=ranking or [],
        metrics=metrics,
        findings=[],
    )


def _languages(
    *,
    distinct: int = 0,
    with_stats: int = 0,
    declared: int = 0,
    unknown: int = 0,
    empty: int = 0,
) -> LanguageDistributionAnalysis:
    return LanguageDistributionAnalysis(
        username="octocat",
        repositories=[],
        distribution=[],
        distinct_languages=distinct,
        total_bytes=0,
        repos_with_stats=with_stats,
        declared_only_count=declared,
        unknown_count=unknown,
        empty_count=empty,
        metrics=[],
        findings=[],
    )


def test_many_stars_and_diverse_languages_score_100() -> None:
    result = VisibilityScorer().score(
        ScoreInputs(
            stars=_stars(total=8000),
            languages=_languages(distinct=8, with_stats=5),
        )
    )
    assert result is not None
    assert result.dimension is DimensionId.VISIBILITY
    assert result.score == 100.0
    assert sum(item.contribution for item in result.breakdown) == pytest.approx(100.0)


def test_stars_only_renormalizes_without_languages() -> None:
    result = VisibilityScorer().score(ScoreInputs(stars=_stars(total=5000)))
    assert result is not None
    assert result.score == 100.0
    assert len(result.breakdown) == 1
    assert result.breakdown[0].component_id == "portfolio_stars"


def test_star_total_falls_back_to_ranking() -> None:
    ranking = [
        StarsRankingEntry(rank=1, full_name="octocat/a", stars=3000, fork=False, archived=False),
        StarsRankingEntry(rank=2, full_name="octocat/b", stars=2000, fork=False, archived=False),
    ]
    result = VisibilityScorer().score(ScoreInputs(stars=_stars(ranking=ranking)))
    assert result is not None
    assert result.score == 100.0


def test_zero_stars_scores_zero() -> None:
    result = VisibilityScorer().score(ScoreInputs(stars=_stars(total=0)))
    assert result is not None
    assert result.score == 0.0


def test_without_stars_analysis_dimension_is_unscorable() -> None:
    assert VisibilityScorer().score(ScoreInputs()) is None
