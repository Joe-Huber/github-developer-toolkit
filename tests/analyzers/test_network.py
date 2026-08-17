"""Tests for followers & network analysis (issue #36)."""

from __future__ import annotations

from datetime import UTC, datetime

from ghdtk.analyzers.network import FollowerNetwork, assess_follower_network
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import (
    DimensionId,
    FindingSeverity,
    MetricAvailability,
    MetricValue,
    SourceEntityKind,
    SourceReference,
)
from ghdtk.models.raw import Follower, ProfileSnapshot, User

NOW = datetime(2026, 1, 1, tzinfo=UTC)

USER_FOLLOWERS_REF = SourceReference(
    entity=SourceEntityKind.USER,
    identifier="octocat",
    field="followers",
)


def _follower(login: str) -> Follower:
    return Follower(login=login)


def _snapshot(
    *,
    followers_count: int | None = 120,
    following_count: int | None = 100,
    followers: list[Follower] | None = None,
    following: list[Follower] | None = None,
    user: User | None = None,
    with_user: bool = True,
) -> ProfileSnapshot:
    resolved_user = user
    if resolved_user is None and with_user:
        resolved_user = User(login="octocat", followers=followers_count, following=following_count)
    return ProfileSnapshot(
        username="octocat",
        collected_at=NOW,
        user=resolved_user,
        followers=followers,
        following=following,
    )


def _metric(result: FollowerNetwork, metric_id: str) -> MetricValue:
    return next(metric.value for metric in result.metrics if metric.id == metric_id)


def _availability(result: FollowerNetwork, metric_id: str) -> MetricAvailability:
    return next(metric.availability for metric in result.metrics if metric.id == metric_id)


def test_balanced_counts_and_ratio() -> None:
    result = assess_follower_network(_snapshot())

    assert result.followers_count == 120
    assert result.following_count == 100
    assert result.ratio == 1.2
    assert _metric(result, "network.followers.count") == 120
    assert _metric(result, "network.following.count") == 100
    assert _metric(result, "network.followers.ratio") == 1.2
    assert not any(
        finding.id in {"network.followers.audience_driven", "network.followers.network_driven"}
        for finding in result.findings
    )


def test_count_metric_carries_provenance() -> None:
    result = assess_follower_network(_snapshot())

    metric = next(m for m in result.metrics if m.id == "network.followers.count")
    assert metric.sources == [USER_FOLLOWERS_REF]
    assert metric.label == "Followers"


def test_audience_driven_profile() -> None:
    result = assess_follower_network(_snapshot(followers_count=900, following_count=100))

    assert result.ratio == 9.0
    finding = next(f for f in result.findings if f.id == "network.followers.audience_driven")
    assert finding.severity is FindingSeverity.INFO
    assert finding.dimension is DimensionId.ENGAGEMENT
    assert "9.0:1" in finding.message


def test_network_driven_profile() -> None:
    result = assess_follower_network(_snapshot(followers_count=10, following_count=100))

    assert result.ratio == 0.1
    finding = next(f for f in result.findings if f.id == "network.followers.network_driven")
    assert finding.severity is FindingSeverity.LOW
    assert finding.dimension is DimensionId.ENGAGEMENT
    assert "0.1:1" in finding.message


def test_zero_follower_profile() -> None:
    result = assess_follower_network(_snapshot(followers_count=0, following_count=5))

    assert result.ratio == 0.0
    finding = next(f for f in result.findings if f.id == "network.followers.zero")
    assert finding.severity is FindingSeverity.INFO
    assert not any(
        finding.id in {"network.followers.audience_driven", "network.followers.network_driven"}
        for finding in result.findings
    )


def test_partial_follower_sample_reports_estimate() -> None:
    followers = [_follower(f"user{i}") for i in range(10)]
    result = assess_follower_network(
        _snapshot(followers_count=50, following_count=100, followers=followers)
    )

    assert result.follower_sample == 10
    assert result.follower_coverage == 0.2
    assert result.reach_estimate == 50
    assert result.reach_confidence == 0.2
    assert _metric(result, "network.followers.sample") == 10
    assert _metric(result, "network.followers.coverage") == 0.2
    assert _metric(result, "network.followers.reach") == 50
    reach_metric = next(m for m in result.metrics if m.id == "network.followers.reach")
    assert reach_metric.confidence == 0.2
    finding = next(f for f in result.findings if f.id == "network.followers.partial_sample")
    assert "10 of 50 followers" in finding.message


def test_full_follower_sample_reports_full_coverage() -> None:
    followers = [_follower(f"user{i}") for i in range(120)]
    result = assess_follower_network(_snapshot(followers=followers))

    assert result.follower_coverage == 1.0
    assert result.reach_confidence == 1.0
    assert not any(finding.id == "network.followers.partial_sample" for finding in result.findings)


def test_mutual_follows_computed_from_samples() -> None:
    followers = [_follower("alice"), _follower("bob"), _follower("carol")]
    following = [_follower("bob"), _follower("carol"), _follower("dave")]
    result = assess_follower_network(
        _snapshot(followers_count=3, following_count=3, followers=followers, following=following)
    )

    assert result.mutual_follows == 2
    assert _metric(result, "network.mutual_follows.count") == 2


def test_mutual_follows_unavailable_when_following_not_collected() -> None:
    result = assess_follower_network(
        _snapshot(followers_count=5, following_count=100, followers=[_follower("alice")])
    )

    assert result.mutual_follows is None
    assert _metric(result, "network.mutual_follows.count") is None
    assert _availability(result, "network.mutual_follows.count") is MetricAvailability.UNAVAILABLE
    finding = next(f for f in result.findings if f.id == "network.mutual_follows.unavailable")
    assert "was not collected" in finding.message


def test_growth_and_org_counts_always_unavailable() -> None:
    result = assess_follower_network(_snapshot())

    assert _metric(result, "network.followers.growth") is None
    assert _metric(result, "network.orgs.count") is None
    assert _availability(result, "network.followers.growth") is MetricAvailability.UNAVAILABLE
    assert _availability(result, "network.orgs.count") is MetricAvailability.UNAVAILABLE
    growth = next(f for f in result.findings if f.id == "network.followers.growth_unavailable")
    assert "never inferred" in growth.message
    orgs = next(f for f in result.findings if f.id == "network.orgs.unavailable")
    assert "does not collect the org list" in orgs.message


def test_missing_user_data_reports_unavailable() -> None:
    result = assess_follower_network(_snapshot(with_user=False))

    assert result.followers_count is None
    assert result.following_count is None
    assert result.ratio is None
    assert result.reach_estimate == 0
    assert _metric(result, "network.followers.count") is None
    assert _metric(result, "network.followers.ratio") is None
    assert _availability(result, "network.followers.count") is MetricAvailability.UNAVAILABLE
    assert _availability(result, "network.followers.ratio") is MetricAvailability.UNAVAILABLE
    assert not any(
        finding.id in {"network.followers.zero", "network.followers.audience_driven"}
        for finding in result.findings
    )


def test_lopsided_threshold_is_config_driven() -> None:
    snapshot = _snapshot(followers_count=250, following_count=100)

    default = assess_follower_network(snapshot)
    assert default.ratio == 2.5
    assert not any(
        finding.id == "network.followers.audience_driven" for finding in default.findings
    )

    strict = assess_follower_network(
        snapshot,
        thresholds=AnalysisThresholds(network_lopsided_ratio=2.0),
    )
    assert any(finding.id == "network.followers.audience_driven" for finding in strict.findings)
