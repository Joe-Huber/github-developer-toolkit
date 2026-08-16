"""Tests for the activity dimension scorer (issue #49)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ghdtk.analyzers.commits import CommitActivity
from ghdtk.models.derived import DimensionId, MetricRecord
from ghdtk.scoring import ScoreInputs
from ghdtk.scoring.scorers.activity import ActivityScorer

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _metric(metric_id: str, value: object) -> MetricRecord:
    return MetricRecord(
        id=metric_id,
        label=metric_id,
        value=value,
        sources=[],
        timestamp=NOW,
    )


def _commits(
    *,
    total: int,
    cadence: float | None,
    active: int,
) -> CommitActivity:
    return CommitActivity(
        username="octocat",
        total_commits=total,
        repos_collected=1,
        repos_with_commits=1,
        active_days=active,
        cadence_per_month=cadence,
        per_repo_commits={},
        weekday_counts={},
        hour_bucket_counts={},
        metrics=[_metric("commit_activity.total_commits", total)],
        findings=[],
    )


def test_high_volume_cadence_and_breadth_scores_100() -> None:
    result = ActivityScorer().score(
        ScoreInputs(commits=_commits(total=2000, cadence=4.0, active=120))
    )
    assert result is not None
    assert result.dimension is DimensionId.ACTIVITY
    assert result.score == 100.0
    assert [item.component_id for item in result.breakdown] == [
        "commit_volume",
        "commit_cadence",
        "active_days",
    ]
    assert sum(item.contribution for item in result.breakdown) == pytest.approx(100.0)


def test_no_commits_scores_zero() -> None:
    result = ActivityScorer().score(ScoreInputs(commits=_commits(total=0, cadence=0.0, active=0)))
    assert result is not None
    assert result.score == 0.0


def test_mid_range_activity() -> None:
    result = ActivityScorer().score(
        ScoreInputs(commits=_commits(total=100, cadence=2.0, active=45))
    )
    assert result is not None
    assert result.score == pytest.approx(56.67, abs=0.005)


def test_without_commit_analysis_dimension_is_unscorable() -> None:
    assert ActivityScorer().score(ScoreInputs()) is None
