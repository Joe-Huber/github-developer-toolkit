"""Star growth & trend analysis from the stargazer timeline (issue #34).

Historical star data is expensive and, for large repositories, inherently
incomplete: the pipeline (issue #22) fetches at most
``MAX_COLLECTION_PAGES`` pages of the most-starred **owned** repository, under
the shared request budget. This analyzer therefore reports growth honestly.

Documented data-availability rules (see the metric availability matrix,
issue #62):

- **What is always reported as an observed fact:** how many stargazers were
  collected, how many the repository reports, and how many starred within the
  last 30/90/365 days. These counts come only from ``starred_at`` values that
  were actually observed; nothing is extrapolated.
- **What requires complete coverage:** growth velocity and the trend verdict.
  They are only computed when the collection record succeeded **and** the
  collected timeline covers the repository's reported stargazer count **and**
  the timeline spans at least two distinct star dates over 30 days. Otherwise
  the status is ``insufficient`` and a finding explains why.
- **No history is ever claimed that was not observed.** When the timeline is
  truncated by the page cap, the missing (older) history is reported as
  missing, never guessed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

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
from ghdtk.models.raw import CollectionStatus, ProfileSnapshot

__all__ = [
    "StarGrowthAnalysis",
    "StarGrowthStatus",
    "assess_star_growth",
]

_MIN_SPAN_DAYS = 30


class StarGrowthStatus(StrEnum):
    """How much of the star history could be relied on."""

    COMPLETE = "complete"
    INSUFFICIENT = "insufficient"
    NO_TIMELINE = "no_timeline"


class StarGrowthAnalysis(BaseModel):
    """Star growth assessment for the collected timeline."""

    model_config = ConfigDict(frozen=True)

    username: str
    status: StarGrowthStatus
    timeline_repo: str | None = None
    observed_stars: int = 0
    reported_stars: int = 0
    coverage: float = 0.0
    metrics: list[MetricRecord]
    findings: list[Finding]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _source(identifier: str, field: str) -> SourceReference:
    return SourceReference(
        entity=SourceEntityKind.REPOSITORY,
        identifier=identifier,
        field=field,
    )


def _round(value: float, digits: int = 3) -> float:
    return round(value, digits)


def assess_star_growth(
    snapshot: ProfileSnapshot,
    *,
    now: datetime | None = None,
    thresholds: AnalysisThresholds | None = None,
) -> StarGrowthAnalysis:
    """Assess star growth from the observed stargazer timeline, honestly."""
    thresholds = thresholds or AnalysisThresholds()
    now = _ensure_utc(now or datetime.now(UTC))
    now_ts = snapshot.collected_at
    stargazers = snapshot.stargazers or []
    observed = [stargazer for stargazer in stargazers if stargazer.starred_at is not None]
    observed_stars = len(observed)
    record = next(
        (r for r in snapshot.collections if r.name.startswith("stargazers:")),
        None,
    )
    metrics: list[MetricRecord] = []
    findings: list[Finding] = []

    timeline_repo: str | None = None
    reported_stars = 0
    coverage = 0.0
    status = StarGrowthStatus.NO_TIMELINE
    trend = "unavailable"

    if record is None:
        findings.append(
            Finding(
                id="star_growth.no_timeline",
                type="informational",
                severity=FindingSeverity.INFO,
                title="No stargazer timeline was collected",
                message=(
                    "Star growth cannot be assessed because no stargazer timeline "
                    "was collected for the most-starred repository."
                ),
                dimension=DimensionId.ENGAGEMENT,
            )
        )
    else:
        timeline_repo = record.name.removeprefix("stargazers:")
        repo = next(
            (r for r in (snapshot.repositories or []) if r.full_name == timeline_repo),
            None,
        )
        reported_stars = (repo.stargazers_count or 0) if repo else 0
        coverage = (
            min(1.0, observed_stars / reported_stars)
            if reported_stars > 0
            else (1.0 if observed_stars == 0 else 0.0)
        )
        dates = sorted(
            {
                _ensure_utc(stargazer.starred_at)
                for stargazer in observed
                if stargazer.starred_at is not None
            }
        )

        if record.status != CollectionStatus.SUCCESS:
            status = StarGrowthStatus.INSUFFICIENT
            findings.append(
                Finding(
                    id="star_growth.insufficient_data",
                    type="informational",
                    severity=FindingSeverity.INFO,
                    title="Star growth data is unavailable",
                    message=(
                        f"The stargazer timeline for {timeline_repo} was not collected "
                        f"({record.reason or record.status}); growth signals are not drawn."
                    ),
                    dimension=DimensionId.ENGAGEMENT,
                    evidence=[_source(timeline_repo, "pushed_at")],
                )
            )
        elif reported_stars == 0:
            status = StarGrowthStatus.INSUFFICIENT
            findings.append(
                Finding(
                    id="star_growth.insufficient_data",
                    type="informational",
                    severity=FindingSeverity.INFO,
                    title="No star history to assess",
                    message=(
                        f"{timeline_repo} reports no stars; there is no observed "
                        "history to draw growth signals from."
                    ),
                    dimension=DimensionId.ENGAGEMENT,
                    evidence=[_source(timeline_repo, "stargazers_count")],
                )
            )
        elif observed_stars < reported_stars:
            status = StarGrowthStatus.INSUFFICIENT
            findings.append(
                Finding(
                    id="star_growth.insufficient_data",
                    type="informational",
                    severity=FindingSeverity.INFO,
                    title="Stargazer timeline is incomplete",
                    message=(
                        f"Only {observed_stars} of {reported_stars} reported stars for "
                        f"{timeline_repo} were observed; growth signals are not drawn."
                    ),
                    dimension=DimensionId.ENGAGEMENT,
                    evidence=[_source(timeline_repo, "stargazers_count")],
                )
            )
        elif len(dates) < 2 or (dates[-1] - dates[0]).days < _MIN_SPAN_DAYS:
            status = StarGrowthStatus.INSUFFICIENT
            span_days = (dates[-1] - dates[0]).days if len(dates) >= 2 else 0
            findings.append(
                Finding(
                    id="star_growth.insufficient_data",
                    type="informational",
                    severity=FindingSeverity.INFO,
                    title="Stargazer timeline is too sparse",
                    message=(
                        f"The timeline for {timeline_repo} spans {span_days} days, "
                        "shorter than the 30-day minimum; growth signals are not drawn."
                    ),
                    dimension=DimensionId.ENGAGEMENT,
                    evidence=[_source(timeline_repo, "pushed_at")],
                )
            )
        else:
            span_days = max(1, (dates[-1] - dates[0]).days)
            recent_count = sum(
                1 for day in dates if day >= now - timedelta(days=thresholds.growth_window_days)
            )
            recent_per_month = recent_count / (thresholds.growth_window_days / 30)
            overall_per_month = observed_stars / (span_days / 30)
            ratio = recent_per_month / overall_per_month
            status = StarGrowthStatus.COMPLETE
            if ratio >= thresholds.trend_rising_ratio:
                trend = "rising"
                findings.append(
                    Finding(
                        id="star_growth.rising",
                        type="standout",
                        severity=FindingSeverity.INFO,
                        title=f"{timeline_repo} is gaining stars quickly",
                        message=(
                            f"Recent star velocity ({recent_per_month:.1f}/month) is "
                            f"{ratio:.1f}x the overall velocity ({overall_per_month:.1f}/month)."
                        ),
                        dimension=DimensionId.ENGAGEMENT,
                        evidence=[_source(timeline_repo, "pushed_at")],
                    )
                )
            elif ratio <= thresholds.trend_slowing_ratio:
                trend = "slowing"
                findings.append(
                    Finding(
                        id="star_growth.slowing",
                        type="quality_issue",
                        severity=FindingSeverity.LOW,
                        title=f"{timeline_repo} star growth has slowed",
                        message=(
                            f"Recent star velocity ({recent_per_month:.1f}/month) is "
                            f"{ratio:.1f}x the overall velocity ({overall_per_month:.1f}/month)."
                        ),
                        dimension=DimensionId.ENGAGEMENT,
                        evidence=[_source(timeline_repo, "pushed_at")],
                    )
                )
            else:
                trend = "stable"

        if status is StarGrowthStatus.INSUFFICIENT:
            trend = "insufficient"

        recent = {
            days: sum(1 for day in dates if day >= now - timedelta(days=days))
            for days in (30, 90, 365)
        }
        metrics = [
            MetricRecord(
                id="star_growth.timeline_repo",
                label="Repository the timeline covers",
                value=timeline_repo,
                timestamp=now_ts,
                sources=[_source(timeline_repo, "pushed_at")],
            ),
            MetricRecord(
                id="star_growth.observed_stars",
                label="Stargazers observed in the timeline",
                value=observed_stars,
                timestamp=now_ts,
                sources=[_source(timeline_repo, "pushed_at")],
            ),
            MetricRecord(
                id="star_growth.reported_stars",
                label="Stars reported by the repository",
                value=reported_stars,
                timestamp=now_ts,
                sources=[_source(timeline_repo, "stargazers_count")],
            ),
            MetricRecord(
                id="star_growth.coverage",
                label="Timeline coverage of reported stars",
                value=_round(coverage),
                timestamp=now_ts,
                sources=[_source(timeline_repo, "pushed_at")],
            ),
            MetricRecord(
                id="star_growth.stars_30d",
                label="Stars added in the last 30 days",
                value=recent[30],
                timestamp=now_ts,
                sources=[_source(timeline_repo, "pushed_at")],
            ),
            MetricRecord(
                id="star_growth.stars_90d",
                label="Stars added in the last 90 days",
                value=recent[90],
                timestamp=now_ts,
                sources=[_source(timeline_repo, "pushed_at")],
            ),
            MetricRecord(
                id="star_growth.stars_365d",
                label="Stars added in the last 365 days",
                value=recent[365],
                timestamp=now_ts,
                sources=[_source(timeline_repo, "pushed_at")],
            ),
            MetricRecord(
                id="star_growth.trend",
                label="Star growth trend",
                value=trend,
                timestamp=now_ts,
                sources=[_source(timeline_repo, "pushed_at")],
            ),
        ]

    return StarGrowthAnalysis(
        username=snapshot.username,
        status=status,
        timeline_repo=timeline_repo,
        observed_stars=observed_stars,
        reported_stars=reported_stars,
        coverage=coverage,
        metrics=metrics,
        findings=findings,
    )
