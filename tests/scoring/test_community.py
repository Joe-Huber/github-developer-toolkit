"""Tests for the community dimension scorer (issue #49)."""

from __future__ import annotations

import pytest

from ghdtk.analyzers.network import FollowerNetwork
from ghdtk.models.derived import DimensionId
from ghdtk.scoring import ScoreInputs
from ghdtk.scoring.scorers.community import CommunityScorer


def _network(
    *,
    followers: int | None = None,
    following: int | None = None,
    ratio: float | None = None,
    reach: float = 0.0,
) -> FollowerNetwork:
    return FollowerNetwork(
        username="octocat",
        followers_count=followers,
        following_count=following,
        ratio=ratio,
        reach_estimate=reach,
        metrics=[],
        findings=[],
    )


def test_balanced_network_scores_100() -> None:
    result = CommunityScorer().score(
        ScoreInputs(network=_network(followers=1000, following=1000, ratio=1.0, reach=8000))
    )
    assert result is not None
    assert result.dimension is DimensionId.ENGAGEMENT
    assert result.score == 100.0
    assert sum(item.contribution for item in result.breakdown) == pytest.approx(100.0)


def test_audience_driven_network_keeps_full_balance_credit() -> None:
    result = CommunityScorer().score(
        ScoreInputs(network=_network(followers=2000, following=1000, ratio=2.0, reach=8000))
    )
    assert result is not None
    assert result.score == pytest.approx(100.0)
    assert sum(item.contribution for item in result.breakdown) == pytest.approx(100.0)


def test_no_followers_scores_zero() -> None:
    result = CommunityScorer().score(ScoreInputs(network=_network(followers=0)))
    assert result is not None
    assert result.score == 0.0


def test_ratio_derived_from_counts_when_unrecorded() -> None:
    result = CommunityScorer().score(
        ScoreInputs(network=_network(followers=100, following=200, ratio=None, reach=0))
    )
    assert result is not None
    assert result.score == pytest.approx(56.67, abs=0.005)


def test_balance_curve_gives_full_credit_within_healthy_band() -> None:
    assert CommunityScorer._balance_score(0.5) == pytest.approx(100.0)
    assert CommunityScorer._balance_score(1.0) == pytest.approx(100.0)
    assert CommunityScorer._balance_score(5.0) == pytest.approx(100.0)


def test_balance_curve_taper_is_gradual_for_popular_profiles() -> None:
    assert CommunityScorer._balance_score(20.0) == pytest.approx(62.4, abs=0.1)
    assert CommunityScorer._balance_score(100.0) == pytest.approx(43.5, abs=0.1)
    assert CommunityScorer._balance_score(float("inf")) == pytest.approx(0.0)


def test_balance_curve_penalizes_reciprocity_lean_only_below_band() -> None:
    assert CommunityScorer._balance_score(0.5) == pytest.approx(100.0)
    assert CommunityScorer._balance_score(0.25) == pytest.approx(50.0)
    assert CommunityScorer._balance_score(0.0) == pytest.approx(0.0)


def test_unavailable_followers_is_unscorable() -> None:
    assert CommunityScorer().score(ScoreInputs(network=_network(followers=None))) is None


def test_without_network_analysis_dimension_is_unscorable() -> None:
    assert CommunityScorer().score(ScoreInputs()) is None
