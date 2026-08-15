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


def test_large_balanced_network_scores_100() -> None:
    result = CommunityScorer().score(
        ScoreInputs(network=_network(followers=2000, following=1000, ratio=2.0, reach=8000))
    )
    assert result is not None
    assert result.dimension is DimensionId.ENGAGEMENT
    assert result.score == 100.0
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
    assert result.score == pytest.approx(41.67, abs=0.005)


def test_unavailable_followers_is_unscorable() -> None:
    assert CommunityScorer().score(ScoreInputs(network=_network(followers=None))) is None


def test_without_network_analysis_dimension_is_unscorable() -> None:
    assert CommunityScorer().score(ScoreInputs()) is None
