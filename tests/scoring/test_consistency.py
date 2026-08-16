"""Tests for the consistency dimension scorer (issue #48)."""

from __future__ import annotations

import pytest

from ghdtk.analyzers.commits import CommitActivity
from ghdtk.analyzers.contribution_calendar import ContributionCalendarAnalysis
from ghdtk.models.derived import DimensionId
from ghdtk.scoring import ScoreInputs
from ghdtk.scoring.scorers.consistency import ConsistencyScorer


def _commits(
    *,
    total: int,
    cadence: float | None = None,
    median_gap: float | None = None,
    span: int | None = None,
    active: int = 0,
) -> CommitActivity:
    return CommitActivity(
        username="octocat",
        total_commits=total,
        repos_collected=1,
        repos_with_commits=1,
        span_days=span,
        active_days=active,
        cadence_per_month=cadence,
        median_gap_days=median_gap,
        per_repo_commits={},
        weekday_counts={},
        hour_bucket_counts={},
        metrics=[],
        findings=[],
    )


def _calendar(
    *,
    total: int | None = None,
    density: float = 0.0,
    longest_streak: int = 0,
    longest_gap: int = 0,
) -> ContributionCalendarAnalysis:
    return ContributionCalendarAnalysis(
        username="octocat",
        total_contributions=total,
        density=density,
        longest_streak=longest_streak,
        longest_gap_days=longest_gap,
        monthly_pattern={},
        yearly_pattern={},
        metrics=[],
        findings=[],
    )


def _strong_calendar() -> ContributionCalendarAnalysis:
    return _calendar(total=4000, density=0.8, longest_streak=25, longest_gap=10)


def _empty_calendar() -> ContributionCalendarAnalysis:
    return _calendar(total=0, density=0.0, longest_streak=0, longest_gap=0)


def test_regular_commits_and_dense_calendar_score_high() -> None:
    commits = _commits(total=100, cadence=4.0, median_gap=7.0, span=100, active=60)
    result = ConsistencyScorer().score(
        ScoreInputs(commits=commits, contribution_calendar=_strong_calendar())
    )
    assert result is not None
    assert result.dimension is DimensionId.CONSISTENCY
    assert result.score == pytest.approx(90.15, abs=0.005)
    assert sum(item.contribution for item in result.breakdown) == pytest.approx(result.score)


def test_commits_only_when_calendar_missing() -> None:
    commits = _commits(total=100, cadence=4.0, median_gap=7.0, span=100, active=60)
    result = ConsistencyScorer().score(ScoreInputs(commits=commits))
    assert result is not None
    assert result.score == 92.0
    assert len(result.breakdown) == 1


def test_no_commits_with_strong_calendar_scores_partial() -> None:
    commits = _commits(total=0, span=100, active=0)
    result = ConsistencyScorer().score(
        ScoreInputs(commits=commits, contribution_calendar=_strong_calendar())
    )
    assert result is not None
    assert result.score == pytest.approx(25.75, abs=0.005)


def test_no_activity_anywhere_scores_zero() -> None:
    commits = _commits(total=0, span=100, active=0)
    result = ConsistencyScorer().score(
        ScoreInputs(commits=commits, contribution_calendar=_empty_calendar())
    )
    assert result is not None
    assert result.score == 0.0


def test_without_commit_analysis_dimension_is_unscorable() -> None:
    assert ConsistencyScorer().score(ScoreInputs()) is None
