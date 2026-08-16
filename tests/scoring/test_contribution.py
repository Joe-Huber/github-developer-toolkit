"""Tests for the contribution dimension scorer (issue #49)."""

from __future__ import annotations

import pytest

from ghdtk.analyzers.contribution_calendar import ContributionCalendarAnalysis
from ghdtk.models.derived import DimensionId
from ghdtk.scoring import ScoreInputs
from ghdtk.scoring.scorers.contribution import ContributionScorer


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


def test_high_volume_density_and_streaks_score_high() -> None:
    result = ContributionScorer().score(
        ScoreInputs(
            contribution_calendar=_calendar(
                total=6000, density=0.9, longest_streak=40, longest_gap=5
            )
        )
    )
    assert result is not None
    assert result.dimension is DimensionId.CONTRIBUTION
    assert result.score == pytest.approx(96.5)
    assert sum(item.contribution for item in result.breakdown) == pytest.approx(result.score)


def test_no_contributions_scores_zero() -> None:
    result = ContributionScorer().score(ScoreInputs(contribution_calendar=_calendar(total=0)))
    assert result is not None
    assert result.score == 0.0


def test_no_calendar_data_scores_zero() -> None:
    result = ContributionScorer().score(ScoreInputs(contribution_calendar=_calendar()))
    assert result is not None
    assert result.score == 0.0


def test_mid_range_contributions() -> None:
    result = ContributionScorer().score(
        ScoreInputs(
            contribution_calendar=_calendar(
                total=500, density=0.5, longest_streak=15, longest_gap=30
            )
        )
    )
    assert result is not None
    assert result.score == pytest.approx(60.71, abs=0.005)


def test_without_calendar_analysis_dimension_is_unscorable() -> None:
    assert ContributionScorer().score(ScoreInputs()) is None
