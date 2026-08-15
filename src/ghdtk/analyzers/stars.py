"""Stars aggregation & distribution analysis (issue #33).

Computes total stars, per-repository stars, percentile distribution and the
most-starred ranking from the repository data collected in #27.

Documented fork policy (shared with the repository analyzers): a fork's stars
are not the user's own work, so every aggregate and the ranking is computed
over **owned** (non-fork) repositories, while ``portfolio.stars.fork_stars``
reports how many of the portfolio's stars come from forks. Archived
repositories keep their stars — stars were earned before archiving — so they
stay in the aggregates and the ranking.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import (
    DimensionId,
    Finding,
    FindingSeverity,
    MetricRecord,
    SourceEntityKind,
    SourceReference,
)
from ghdtk.models.raw import ProfileSnapshot

__all__ = ["StarsAnalysis", "StarsRankingEntry", "assess_star_distribution"]

_BUCKETS = ((0, 0), (1, 9), (10, 99), (100, 999), (1000, None))


def _source(identifier: str, field: str) -> SourceReference:
    return SourceReference(
        entity=SourceEntityKind.REPOSITORY,
        identifier=identifier,
        field=field,
    )


def _percentile(sorted_values: list[int], percentile: float) -> float:
    """Nearest-rank percentile over ascending values; 0.0 for an empty set."""
    if not sorted_values:
        return 0.0
    rank = max(1, math.ceil(percentile / 100 * len(sorted_values)))
    return float(sorted_values[rank - 1])


def _median(sorted_values: list[int]) -> float:
    """Conventional median: mean of the two middle values for an even count."""
    if not sorted_values:
        return 0.0
    middle = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return float(sorted_values[middle])
    return (sorted_values[middle - 1] + sorted_values[middle]) / 2


def _bucket(stars: int) -> tuple[int, int | None]:
    for low, high in _BUCKETS:
        if high is None or stars <= high:
            return (low, high)
    raise AssertionError("unreachable bucket")


class StarsRankingEntry(BaseModel):
    """One repository's position in the most-starred ranking."""

    model_config = ConfigDict(frozen=True)

    rank: int
    full_name: str
    stars: int
    fork: bool
    archived: bool


class StarsAnalysis(BaseModel):
    """Portfolio star aggregation, distribution and ranking."""

    model_config = ConfigDict(frozen=True)

    username: str
    ranking: list[StarsRankingEntry]
    metrics: list[MetricRecord]
    findings: list[Finding]


def assess_star_distribution(
    snapshot: ProfileSnapshot,
    *,
    thresholds: AnalysisThresholds | None = None,
) -> StarsAnalysis:
    """Aggregate stars, distribution percentiles and the most-starred ranking."""
    thresholds = thresholds or AnalysisThresholds()
    repositories = snapshot.repositories or []
    owned = [repo for repo in repositories if not repo.fork]
    forks = [repo for repo in repositories if repo.fork]
    now_ts = snapshot.collected_at

    owned_stars = sorted((repo.stargazers_count or 0) for repo in owned)
    total = sum(owned_stars)
    fork_stars = sum(repo.stargazers_count or 0 for repo in forks)
    counts = {
        (low, high): sum(1 for stars in owned_stars if _bucket(stars) == (low, high))
        for low, high in _BUCKETS
    }
    with_stars = sum(1 for stars in owned_stars if stars >= 1)

    ranking = [
        StarsRankingEntry(
            rank=position,
            full_name=repo.full_name or "",
            stars=repo.stargazers_count or 0,
            fork=bool(repo.fork),
            archived=bool(repo.archived),
        )
        for position, repo in enumerate(
            sorted(owned, key=lambda item: (-(item.stargazers_count or 0), item.full_name or "")),
            start=1,
        )
    ]

    bucket_sources = [_source(repo.full_name or "", "stargazers_count") for repo in owned]
    metrics = [
        MetricRecord(
            id="portfolio.stars.total",
            label="Total stars (owned repositories)",
            value=total,
            timestamp=now_ts,
            sources=bucket_sources,
        ),
        MetricRecord(
            id="portfolio.stars.fork_stars",
            label="Stars from forked repositories",
            value=fork_stars,
            timestamp=now_ts,
            sources=[_source(repo.full_name or "", "stargazers_count") for repo in forks],
        ),
        MetricRecord(
            id="portfolio.stars.average",
            label="Average stars per owned repository",
            value=round(total / len(owned_stars), 2) if owned_stars else 0.0,
            timestamp=now_ts,
            sources=bucket_sources,
        ),
        MetricRecord(
            id="portfolio.stars.median",
            label="Median stars per owned repository",
            value=_median(owned_stars),
            timestamp=now_ts,
            sources=bucket_sources,
        ),
        MetricRecord(
            id="portfolio.stars.p25",
            label="25th percentile of stars",
            value=_percentile(owned_stars, 25),
            timestamp=now_ts,
            sources=bucket_sources,
        ),
        MetricRecord(
            id="portfolio.stars.p75",
            label="75th percentile of stars",
            value=_percentile(owned_stars, 75),
            timestamp=now_ts,
            sources=bucket_sources,
        ),
        MetricRecord(
            id="portfolio.stars.p90",
            label="90th percentile of stars",
            value=_percentile(owned_stars, 90),
            timestamp=now_ts,
            sources=bucket_sources,
        ),
        MetricRecord(
            id="portfolio.stars.p99",
            label="99th percentile of stars",
            value=_percentile(owned_stars, 99),
            timestamp=now_ts,
            sources=bucket_sources,
        ),
        MetricRecord(
            id="portfolio.stars.max",
            label="Most stars in a single repository",
            value=owned_stars[-1] if owned_stars else 0,
            timestamp=now_ts,
            sources=bucket_sources,
        ),
        MetricRecord(
            id="portfolio.stars.repos_with_stars",
            label="Owned repositories with at least one star",
            value=with_stars,
            timestamp=now_ts,
            sources=bucket_sources,
        ),
        MetricRecord(
            id="portfolio.stars.repos_zero",
            label="Owned repositories without stars",
            value=len(owned_stars) - with_stars,
            timestamp=now_ts,
            sources=bucket_sources,
        ),
        *[
            MetricRecord(
                id=(
                    "portfolio.stars.bucket_0"
                    if low == 0
                    else f"portfolio.stars.bucket_{low}_{high or 'plus'}"
                ),
                label=f"Repositories with {low} to {high if high is not None else '+'} stars",
                value=counts[(low, high)],
                timestamp=now_ts,
                sources=bucket_sources,
            )
            for low, high in _BUCKETS
        ],
    ]

    findings: list[Finding] = []
    if owned_stars and total == 0:
        findings.append(
            Finding(
                id="portfolio.stars.no_stars",
                type="informational",
                severity=FindingSeverity.INFO,
                title="No repository in the portfolio has stars",
                message=(
                    f"None of the {len(owned_stars)} owned repositories has a star; "
                    "the portfolio has no star-derived popularity signal."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=bucket_sources,
            )
        )

    all_stars = total + fork_stars
    if fork_stars and all_stars and fork_stars / all_stars > thresholds.fork_ratio_threshold:
        findings.append(
            Finding(
                id="portfolio.stars.fork_star_share",
                type="quality_issue",
                severity=FindingSeverity.LOW,
                title="Most of the portfolio's stars come from forks",
                message=(
                    f"{fork_stars} of {all_stars} stars ({fork_stars / all_stars:.0%}) belong "
                    f"to forked repositories, above the "
                    f"{thresholds.fork_ratio_threshold:.0%} fork-ratio threshold."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=[_source(repo.full_name or "", "stargazers_count") for repo in forks],
            )
        )

    return StarsAnalysis(
        username=snapshot.username,
        ranking=ranking,
        metrics=metrics,
        findings=findings,
    )
