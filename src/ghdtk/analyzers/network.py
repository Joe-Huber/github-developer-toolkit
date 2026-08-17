"""Followers & network analysis (issue #36).

Network metrics from the current follower/following counts and the collected
follower/following lists, with honest labels on every estimate.

Documented interpretation & availability rules:

- **Counts and ratio.** ``network.followers.count`` /
  ``network.following.count`` come from the raw user object. The ratio is
  ``followers / following`` and is interpreted directionally: well above 1 is
  an audience-driven profile, well below 1 a network-driven one, and a
  follower/following ratio near 1 is balanced. When the user object is absent
  or a count is missing, the metric is ``unavailable`` with rationale.
- **Reach is an estimate.** The follower list is paginated and capped by the
  collection page cap, so ``network.followers.reach`` is the reported
  follower count with a confidence equal to the observed coverage; a partial
  sample is reported as an estimate, never as the full audience.
- **Mutual follows.** Computed as the intersection of the collected follower
  and following samples, and therefore an *estimate* unless both lists fully
  cover their reported counts. When the following list was not collected,
  mutual follows are ``unavailable`` with rationale.
- **Org memberships.** Not collected by the pipeline, so the count is
  ``unavailable`` with rationale (the public user object exposes no
  membership count).
- **Growth history is unavailable.** GitHub's API exposes only current
  counts; growth is never invented. ``network.followers.growth`` returns
  ``unavailable`` with a rationale, leaving a hook for archived snapshots.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import (
    DimensionId,
    Finding,
    FindingSeverity,
    MetricAvailability,
    MetricRecord,
    SourceEntityKind,
    SourceReference,
)
from ghdtk.models.raw import ProfileSnapshot

__all__ = ["FollowerNetwork", "assess_follower_network"]


def _source(identifier: str, field: str) -> SourceReference:
    return SourceReference(
        entity=SourceEntityKind.USER,
        identifier=identifier,
        field=field,
    )


class FollowerNetwork(BaseModel):
    """Followers, ratio, reach and availability assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    followers_count: int | None = None
    following_count: int | None = None
    ratio: float | None = None
    follower_sample: int = 0
    follower_coverage: float = 0.0
    reach_estimate: float = 0.0
    reach_confidence: float = 0.0
    mutual_follows: int | None = None
    orgs_count: int | None = None
    metrics: list[MetricRecord]
    findings: list[Finding]


def _coverage(sample: int, reported: int | None) -> float:
    if reported is None:
        return 0.0
    if reported == 0:
        return 1.0 if sample == 0 else 0.0
    return min(1.0, sample / reported)


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)


def assess_follower_network(
    snapshot: ProfileSnapshot,
    *,
    thresholds: AnalysisThresholds | None = None,
) -> FollowerNetwork:
    """Assess follower counts, ratio, reach and availability."""
    thresholds = thresholds or AnalysisThresholds()
    now_ts = snapshot.collected_at
    username = snapshot.username
    user = snapshot.user
    findings: list[Finding] = []

    followers_count = user.followers if user else None
    following_count = user.following if user else None
    ratio: float | None = None
    if following_count and followers_count is not None:
        ratio = _round(followers_count / following_count)

    followers = snapshot.followers or []
    following = snapshot.following or []
    follower_sample = len(followers)
    following_sample = len(following)
    follower_coverage = _coverage(follower_sample, followers_count)
    following_coverage = _coverage(following_sample, following_count)
    reach = float(followers_count) if followers_count is not None else 0.0
    reach_confidence = follower_coverage

    if followers_count is not None:
        if followers_count == 0:
            findings.append(
                Finding(
                    id="network.followers.zero",
                    type="informational",
                    severity=FindingSeverity.INFO,
                    title="The profile has no followers yet",
                    message=(
                        "No one follows the profile yet; there is no follower-based "
                        "audience signal to draw from."
                    ),
                    dimension=DimensionId.ENGAGEMENT,
                    evidence=[_source(username, "followers")],
                )
            )
        elif ratio is not None and ratio >= thresholds.network_lopsided_ratio:
            findings.append(
                Finding(
                    id="network.followers.audience_driven",
                    type="standout",
                    severity=FindingSeverity.INFO,
                    title="Audience-driven profile",
                    message=(
                        f"{followers_count} followers against {following_count} followed "
                        f"({ratio:.1f}:1), well above the "
                        f"{thresholds.network_lopsided_ratio:.0f}:1 lopsided threshold."
                    ),
                    dimension=DimensionId.ENGAGEMENT,
                    evidence=[_source(username, "followers")],
                )
            )
        elif ratio is not None and ratio <= 1 / thresholds.network_lopsided_ratio:
            findings.append(
                Finding(
                    id="network.followers.network_driven",
                    type="quality_issue",
                    severity=FindingSeverity.LOW,
                    title="Profile follows far more than it is followed",
                    message=(
                        f"{followers_count} followers against {following_count} followed "
                        f"({ratio:.1f}:1), at or below the "
                        f"{1 / thresholds.network_lopsided_ratio:.2f}:1 reciprocal threshold."
                    ),
                    dimension=DimensionId.ENGAGEMENT,
                    evidence=[_source(username, "following")],
                )
            )

    if followers_count and follower_sample < followers_count:
        findings.append(
            Finding(
                id="network.followers.partial_sample",
                type="informational",
                severity=FindingSeverity.INFO,
                title="Follower list was only partially collected",
                message=(
                    f"{follower_sample} of {followers_count} followers were observed; "
                    "the reach figure is an estimate, not the full audience."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=[_source(username, "followers")],
            )
        )

    mutual_follows: int | None = None
    if snapshot.following is None:
        findings.append(
            Finding(
                id="network.mutual_follows.unavailable",
                type="informational",
                severity=FindingSeverity.INFO,
                title="Mutual-follow count is unavailable",
                message=(
                    "The following list was not collected, so mutual follows cannot be computed."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=[_source(username, "following")],
            )
        )
    elif followers:
        follower_logins = {f.login for f in followers if f.login}
        following_logins = {f.login for f in following if f.login}
        mutual_follows = len(follower_logins & following_logins)

    findings.append(
        Finding(
            id="network.followers.growth_unavailable",
            type="informational",
            severity=FindingSeverity.INFO,
            title="Follower growth history is unavailable",
            message=(
                "GitHub's API exposes only current follower/following counts; "
                "growth history is not available and is never inferred. This is a "
                "future hook for comparing archived snapshots."
            ),
            dimension=DimensionId.ENGAGEMENT,
            evidence=[_source(username, "followers")],
        )
    )

    findings.append(
        Finding(
            id="network.orgs.unavailable",
            type="informational",
            severity=FindingSeverity.INFO,
            title="Org membership count is unavailable",
            message=(
                "The public user object exposes no org membership count and the "
                "pipeline does not collect the org list; the count cannot be drawn."
            ),
            dimension=DimensionId.ENGAGEMENT,
            evidence=[_source(username, "organizations_url")],
        )
    )

    followers_source = _source(username, "followers")
    following_source = _source(username, "following")
    mutual_source = _source(username, "following")
    metrics = [
        MetricRecord(
            id="network.followers.count",
            label="Followers",
            value=followers_count,
            availability=(
                MetricAvailability.AVAILABLE
                if followers_count is not None
                else MetricAvailability.UNAVAILABLE
            ),
            timestamp=now_ts,
            sources=[followers_source],
        ),
        MetricRecord(
            id="network.following.count",
            label="Following",
            value=following_count,
            availability=(
                MetricAvailability.AVAILABLE
                if following_count is not None
                else MetricAvailability.UNAVAILABLE
            ),
            timestamp=now_ts,
            sources=[following_source],
        ),
        MetricRecord(
            id="network.followers.ratio",
            label="Followers to following ratio",
            value=ratio,
            availability=(
                MetricAvailability.AVAILABLE
                if ratio is not None
                else MetricAvailability.UNAVAILABLE
            ),
            timestamp=now_ts,
            sources=[followers_source, following_source],
        ),
        MetricRecord(
            id="network.followers.sample",
            label="Followers observed in the collected list",
            value=follower_sample,
            timestamp=now_ts,
            sources=[followers_source],
        ),
        MetricRecord(
            id="network.followers.coverage",
            label="Follower list coverage",
            value=_round(follower_coverage),
            timestamp=now_ts,
            sources=[followers_source],
        ),
        MetricRecord(
            id="network.followers.reach",
            label="Estimated follower audience reach",
            value=reach,
            timestamp=now_ts,
            confidence=reach_confidence,
            sources=[followers_source],
        ),
        MetricRecord(
            id="network.mutual_follows.count",
            label="Mutual follows (estimated from samples)",
            value=mutual_follows,
            availability=(
                MetricAvailability.PARTIAL
                if mutual_follows is not None
                else MetricAvailability.UNAVAILABLE
            ),
            timestamp=now_ts,
            confidence=min(follower_coverage, following_coverage),
            sources=[mutual_source],
        ),
        MetricRecord(
            id="network.orgs.count",
            label="Org memberships",
            value=None,
            availability=MetricAvailability.UNAVAILABLE,
            timestamp=now_ts,
            sources=[_source(username, "organizations_url")],
        ),
        MetricRecord(
            id="network.followers.growth",
            label="Follower growth",
            value=None,
            availability=MetricAvailability.UNAVAILABLE,
            timestamp=now_ts,
            sources=[followers_source],
        ),
    ]

    return FollowerNetwork(
        username=username,
        followers_count=followers_count,
        following_count=following_count,
        ratio=ratio,
        follower_sample=follower_sample,
        follower_coverage=_round(follower_coverage),
        reach_estimate=reach,
        reach_confidence=reach_confidence,
        mutual_follows=mutual_follows,
        orgs_count=None,
        metrics=metrics,
        findings=findings,
    )
