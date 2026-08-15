"""Tests for the repository dimension scorer (issue #48)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ghdtk.analyzers.portfolio import (
    PortfolioComposition,
    RepositoryCompositionSignals,
)
from ghdtk.analyzers.repository_activity import (
    RepositoryActivity,
    RepositoryActivitySignals,
)
from ghdtk.analyzers.repository_quality import (
    ReadmeState,
    RepositoryQuality,
    RepositoryQualitySignals,
)
from ghdtk.models.derived import DimensionId, MetricRecord
from ghdtk.scoring import ScoreInputs
from ghdtk.scoring.scorers.repository import RepositoryScorer

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _metric(metric_id: str, value: object) -> MetricRecord:
    return MetricRecord(
        id=metric_id,
        label=metric_id,
        value=value,
        sources=[],
        timestamp=NOW,
    )


def _quality(metrics: list[MetricRecord], count: int = 2) -> RepositoryQuality:
    signals = [
        RepositoryQualitySignals(
            full_name=f"octocat/repo{i}",
            has_description=True,
            description_placeholder=False,
            readme=ReadmeState.PRESENT,
            readme_chars=500,
            topics_count=3,
            has_license=True,
            has_homepage=True,
        )
        for i in range(count)
    ]
    return RepositoryQuality(username="octocat", signals=signals, metrics=metrics, findings=[])


def _activity(metrics: list[MetricRecord]) -> RepositoryActivity:
    return RepositoryActivity(
        username="octocat",
        signals=[RepositoryActivitySignals(full_name="octocat/repo", fork=False, archived=False)],
        metrics=metrics,
        findings=[],
    )


def _portfolio(standouts: list[str], metrics: list[MetricRecord]) -> PortfolioComposition:
    return PortfolioComposition(
        username="octocat",
        signals=[
            RepositoryCompositionSignals(
                full_name="octocat/repo", stars=0, fork=False, archived=False
            )
        ],
        standouts=standouts,
        metrics=metrics,
        findings=[],
    )


def _perfect_quality() -> list[MetricRecord]:
    return [
        _metric("portfolio.quality.description_coverage", 1.0),
        _metric("portfolio.quality.readme_coverage", 1.0),
        _metric("portfolio.quality.license_coverage", 1.0),
        _metric("portfolio.quality.homepage_coverage", 1.0),
        _metric("portfolio.quality.topics.average", 5.0),
    ]


def _perfect_activity() -> list[MetricRecord]:
    return [
        _metric("portfolio.activity.repos.total", 4),
        _metric("portfolio.activity.repos.active", 4),
        _metric("portfolio.activity.median_staleness_days", 0),
    ]


def test_perfect_quality_activity_and_portfolio_scores_100() -> None:
    inputs = ScoreInputs(
        repository_quality=_quality(_perfect_quality()),
        repository_activity=_activity(_perfect_activity()),
        portfolio=_portfolio(
            ["octocat/a", "octocat/b", "octocat/c"],
            [_metric("portfolio.composition.total_stars", 8000)],
        ),
    )
    result = RepositoryScorer().score(inputs)
    assert result is not None
    assert result.dimension is DimensionId.CODE_QUALITY
    assert result.score == 100.0
    assert [item.component_id for item in result.breakdown] == [
        "repository_quality",
        "repository_activity",
        "portfolio_composition",
    ]
    assert sum(item.contribution for item in result.breakdown) == pytest.approx(100.0)


def test_all_zero_signals_score_zero() -> None:
    quality = _quality(
        [
            _metric("portfolio.quality.description_coverage", 0.0),
            _metric("portfolio.quality.readme_coverage", 0.0),
            _metric("portfolio.quality.license_coverage", 0.0),
            _metric("portfolio.quality.homepage_coverage", 0.0),
            _metric("portfolio.quality.topics.average", 0.0),
        ]
    )
    activity = _activity(
        [
            _metric("portfolio.activity.repos.total", 4),
            _metric("portfolio.activity.repos.active", 0),
            _metric("portfolio.activity.median_staleness_days", 100),
        ]
    )
    portfolio = _portfolio([], [_metric("portfolio.composition.total_stars", 0)])
    inputs = ScoreInputs(
        repository_quality=quality,
        repository_activity=activity,
        portfolio=portfolio,
    )
    assert RepositoryScorer().score(inputs) is not None
    result = RepositoryScorer().score(inputs)
    assert result is not None
    assert result.score == 0.0


def test_quality_only_blend_when_other_analyses_missing() -> None:
    result = RepositoryScorer().score(ScoreInputs(repository_quality=_quality(_perfect_quality())))
    assert result is not None
    assert result.score == 100.0
    assert len(result.breakdown) == 1
    assert result.breakdown[0].component_id == "repository_quality"


def test_blended_mid_range_score() -> None:
    quality = _quality(
        [
            _metric("portfolio.quality.description_coverage", 1.0),
            _metric("portfolio.quality.readme_coverage", 0.5),
            _metric("portfolio.quality.license_coverage", 0.0),
            _metric("portfolio.quality.homepage_coverage", 0.0),
            _metric("portfolio.quality.topics.average", 2.0),
        ]
    )
    activity = _activity(
        [
            _metric("portfolio.activity.repos.total", 4),
            _metric("portfolio.activity.repos.active", 2),
            _metric("portfolio.activity.median_staleness_days", 30),
        ]
    )
    portfolio = _portfolio([], [_metric("portfolio.composition.total_stars", 100)])
    inputs = ScoreInputs(
        repository_quality=quality,
        repository_activity=activity,
        portfolio=portfolio,
    )
    result = RepositoryScorer().score(inputs)
    assert result is not None
    assert result.score == pytest.approx(48.90, abs=0.005)


def test_no_repositories_scores_zero() -> None:
    quality = _quality([], count=0)
    activity = _activity(
        [
            _metric("portfolio.activity.repos.total", 0),
            _metric("portfolio.activity.repos.active", 0),
        ]
    )
    result = RepositoryScorer().score(
        ScoreInputs(repository_quality=quality, repository_activity=activity)
    )
    assert result is not None
    assert result.score == 0.0


def test_without_repository_quality_dimension_is_unscorable() -> None:
    assert RepositoryScorer().score(ScoreInputs()) is None
