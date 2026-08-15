"""Portfolio composition & standout identification analysis (issue #31).

Derives portfolio-level signals from the repository set: star concentration,
fork ratio, and the standout repositories a profile leads with.

Documented heuristic policy:

- **Standout repository**: an owned, non-archived repository with at least
  ``standout_star_threshold`` stars that was pushed within
  ``standout_active_days``. A star-heavy but long-abandoned repository is not
  a standout, and neither is a fork.
- **Star concentration** is measured over owned, non-archived repositories:
  when the single most-starred repository holds more than
  ``concentration_top_share`` of the portfolio's stars, that is reported as a
  concentration signal.
- **Fork ratio** is the share of all portfolio repositories that are forks;
  when it exceeds ``fork_ratio_threshold`` the portfolio reads as mostly
  forks.
- With fewer than ``minimum_repositories`` repositories the composition
  conclusions are weak, so an informational finding is emitted and no
  concentration verdict is drawn.
"""

from __future__ import annotations

from datetime import UTC, datetime

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

__all__ = [
    "PortfolioComposition",
    "RepositoryCompositionSignals",
    "assess_portfolio_composition",
]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _days_between(later: datetime, earlier: datetime) -> int:
    return max(0, int((_ensure_utc(later) - _ensure_utc(earlier)).total_seconds() // 86400))


def _source(identifier: str, field: str) -> SourceReference:
    return SourceReference(
        entity=SourceEntityKind.REPOSITORY,
        identifier=identifier,
        field=field,
    )


class RepositoryCompositionSignals(BaseModel):
    """One repository's composition & standout signals."""

    model_config = ConfigDict(frozen=True)

    full_name: str
    stars: int
    fork: bool
    archived: bool
    staleness_days: int | None = None
    standout: bool = False


class PortfolioComposition(BaseModel):
    """Portfolio composition and standout assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    signals: list[RepositoryCompositionSignals]
    standouts: list[str]
    metrics: list[MetricRecord]
    findings: list[Finding]


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)


def assess_portfolio_composition(
    snapshot: ProfileSnapshot,
    *,
    now: datetime | None = None,
    thresholds: AnalysisThresholds | None = None,
) -> PortfolioComposition:
    """Assess composition, concentration and standout repositories."""
    thresholds = thresholds or AnalysisThresholds()
    now = _ensure_utc(now or datetime.now(UTC))
    repositories = snapshot.repositories or []
    signals: list[RepositoryCompositionSignals] = []
    standouts: list[str] = []
    findings: list[Finding] = []

    for repo in repositories:
        pushed = repo.pushed_at or repo.updated_at
        signals.append(
            RepositoryCompositionSignals(
                full_name=repo.full_name or "",
                stars=repo.stargazers_count or 0,
                fork=bool(repo.fork),
                archived=bool(repo.archived),
                staleness_days=_days_between(now, pushed) if pushed else None,
            )
        )

    total = len(signals)
    if total >= thresholds.minimum_repositories:
        for signal in signals:
            if (
                not signal.fork
                and not signal.archived
                and signal.stars >= thresholds.standout_star_threshold
                and signal.staleness_days is not None
                and signal.staleness_days <= thresholds.standout_active_days
            ):
                standouts.append(signal.full_name)
                findings.append(
                    Finding(
                        id=f"repo.standout.{signal.full_name}",
                        type="standout",
                        severity=FindingSeverity.INFO,
                        title=f"{signal.full_name} is a standout repository",
                        message=(
                            f"Owned, recently active, with {signal.stars} stars at or above "
                            f"the {thresholds.standout_star_threshold}-star standout threshold."
                        ),
                        dimension=DimensionId.ENGAGEMENT,
                        evidence=[_source(signal.full_name, "stargazers_count")],
                    )
                )
        signals = [
            signal.model_copy(update={"standout": signal.full_name in standouts})
            for signal in signals
        ]

    now_ts = snapshot.collected_at
    total = len(signals)
    fork_count = sum(1 for signal in signals if signal.fork)
    archived_count = sum(1 for signal in signals if signal.archived)
    scored = [signal for signal in signals if not signal.fork and not signal.archived]
    total_stars = sum(signal.stars for signal in scored)
    top_repo_stars = max((signal.stars for signal in scored), default=0)
    top_repo_share = _round(top_repo_stars / total_stars) if total_stars > 0 else 0.0
    fork_ratio = _round(fork_count / total) if total > 0 else 0.0

    metrics = [
        MetricRecord(
            id="portfolio.composition.repos.total",
            label="Repositories total",
            value=total,
            timestamp=now_ts,
            sources=[_source(s.full_name, "name") for s in signals],
        ),
        MetricRecord(
            id="portfolio.composition.own_count",
            label="Owned repositories",
            value=total - fork_count,
            timestamp=now_ts,
            sources=[_source(s.full_name, "fork") for s in signals],
        ),
        MetricRecord(
            id="portfolio.composition.fork_count",
            label="Forked repositories",
            value=fork_count,
            timestamp=now_ts,
            sources=[_source(s.full_name, "fork") for s in signals if s.fork],
        ),
        MetricRecord(
            id="portfolio.composition.archived_count",
            label="Archived repositories",
            value=archived_count,
            timestamp=now_ts,
            sources=[_source(s.full_name, "archived") for s in signals if s.archived],
        ),
        MetricRecord(
            id="portfolio.composition.fork_ratio",
            label="Fork ratio",
            value=fork_ratio,
            timestamp=now_ts,
            sources=[_source(s.full_name, "fork") for s in signals],
        ),
        MetricRecord(
            id="portfolio.composition.total_stars",
            label="Total stars (owned, non-archived)",
            value=total_stars,
            timestamp=now_ts,
            sources=[_source(s.full_name, "stargazers_count") for s in scored],
        ),
        MetricRecord(
            id="portfolio.composition.top_repo_stars",
            label="Most-starred repository",
            value=top_repo_stars,
            timestamp=now_ts,
            sources=[_source(s.full_name, "stargazers_count") for s in scored],
        ),
        MetricRecord(
            id="portfolio.composition.top_repo_share",
            label="Share of stars held by the most-starred repository",
            value=top_repo_share,
            timestamp=now_ts,
            sources=[_source(s.full_name, "stargazers_count") for s in scored],
        ),
        MetricRecord(
            id="portfolio.standout.count",
            label="Standout repositories",
            value=len(standouts),
            timestamp=now_ts,
            sources=[_source(s, "stargazers_count") for s in standouts],
        ),
        MetricRecord(
            id="portfolio.standout.total_stars",
            label="Stars across standouts",
            value=sum(signal.stars for signal in signals if signal.standout),
            timestamp=now_ts,
            sources=[_source(s, "stargazers_count") for s in standouts],
        ),
    ]

    if total < thresholds.minimum_repositories:
        findings.append(
            Finding(
                id="portfolio.composition.small_portfolio",
                type="informational",
                severity=FindingSeverity.INFO,
                title="Too few repositories for composition analysis",
                message=(
                    f"{total} repositories is below the "
                    f"{thresholds.minimum_repositories}-repository minimum; "
                    "concentration and standout signals are not drawn."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=[_source(s.full_name, "name") for s in signals],
            )
        )
    elif total_stars > 0 and top_repo_share > thresholds.concentration_top_share:
        dominant = scored[0]
        findings.append(
            Finding(
                id="portfolio.composition.star_concentration",
                type="quality_issue",
                severity=FindingSeverity.LOW,
                title="Stars are concentrated in one repository",
                message=(
                    f"{dominant.full_name} holds {top_repo_share:.0%} of the "
                    "portfolio's stars, above the "
                    f"{thresholds.concentration_top_share:.0%} concentration threshold."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=[_source(dominant.full_name, "stargazers_count")],
            )
        )

    if fork_ratio > thresholds.fork_ratio_threshold:
        findings.append(
            Finding(
                id="portfolio.composition.fork_dominated",
                type="quality_issue",
                severity=FindingSeverity.LOW,
                title="Portfolio is dominated by forks",
                message=(
                    f"{fork_count} of {total} repositories are forks "
                    f"({fork_ratio:.0%}), above the "
                    f"{thresholds.fork_ratio_threshold:.0%} fork-ratio threshold."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=[_source(s.full_name, "fork") for s in signals if s.fork],
            )
        )

    if total >= thresholds.minimum_repositories and scored and not standouts:
        findings.append(
            Finding(
                id="portfolio.standout.none_identified",
                type="informational",
                severity=FindingSeverity.INFO,
                title="No standout repositories identified",
                message=(
                    f"No owned, recently active repository reached the "
                    f"{thresholds.standout_star_threshold}-star threshold within "
                    f"{thresholds.standout_active_days} days."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=[_source(s.full_name, "stargazers_count") for s in scored],
            )
        )

    return PortfolioComposition(
        username=snapshot.username,
        signals=signals,
        standouts=standouts,
        metrics=metrics,
        findings=findings,
    )
