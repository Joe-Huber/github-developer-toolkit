"""Repository activity, age & consistency analysis (issue #30).

Portfolio maintenance signals derived from ``created_at`` (age) and
``pushed_at`` (last activity), with configurable staleness thresholds
(:class:`~ghdtk.analyzers.thresholds.AnalysisThresholds`).

Documented handling policy for the portfolio shape:

- **Forked repositories** are not the user's own code, so they are excluded
  from age/staleness/recency metrics and findings, and only reported as a
  count (``portfolio.activity.forked_repos``).
- **Archived repositories** are intentionally frozen: each gets an
  ``info``-level finding, but they are excluded from staleness/recency
  findings so an archive does not read as neglect.
- A repository with no ``pushed_at`` is treated as having unknown recency and
  excluded from active/dormant counts.
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
    "RepositoryActivity",
    "RepositoryActivitySignals",
    "assess_repository_activity",
]

_RECENT_BUCKET_DAYS = 30
_LONG_INACTIVE_DAYS = 365


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


class RepositoryActivitySignals(BaseModel):
    """One repository's activity signals with the documented fork/archive policy applied."""

    model_config = ConfigDict(frozen=True)

    full_name: str
    age_days: int | None = None
    staleness_days: int | None = None
    fork: bool
    archived: bool
    active: bool = False
    stale: bool = False
    unknown: bool = False


class RepositoryActivity(BaseModel):
    """The portfolio activity & consistency assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    signals: list[RepositoryActivitySignals]
    metrics: list[MetricRecord]
    findings: list[Finding]


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def assess_repository_activity(
    snapshot: ProfileSnapshot,
    *,
    now: datetime | None = None,
    thresholds: AnalysisThresholds | None = None,
) -> RepositoryActivity:
    """Assess age, activity and consistency across the portfolio."""
    thresholds = thresholds or AnalysisThresholds()
    now = _ensure_utc(now or datetime.now(UTC))
    repositories = snapshot.repositories or []
    signals: list[RepositoryActivitySignals] = []
    findings: list[Finding] = []

    for repo in repositories:
        full_name = repo.full_name or ""
        pushed = repo.pushed_at or repo.updated_at
        age_days = _days_between(now, repo.created_at) if repo.created_at else None
        staleness_days = _days_between(now, pushed) if pushed else None
        own = not repo.fork
        if own and not repo.archived and staleness_days is not None:
            active = staleness_days <= thresholds.staleness_days
            stale = not active
        else:
            active = False
            stale = False
        signals.append(
            RepositoryActivitySignals(
                full_name=full_name,
                age_days=age_days,
                staleness_days=staleness_days,
                fork=bool(repo.fork),
                archived=bool(repo.archived),
                active=active,
                stale=stale,
                unknown=own and staleness_days is None,
            )
        )

        if repo.archived:
            findings.append(
                Finding(
                    id=f"repo.activity.archived.{full_name}",
                    type="informational",
                    severity=FindingSeverity.INFO,
                    title=f"{full_name} is archived",
                    message=(
                        "The repository is archived and intentionally frozen; "
                        "it is excluded from recency signals."
                    ),
                    dimension=DimensionId.ACTIVITY,
                    evidence=[_source(full_name, "archived")],
                )
            )
        elif stale:
            findings.append(
                Finding(
                    id=f"repo.activity.stale.{full_name}",
                    type="quality_issue",
                    severity=FindingSeverity.LOW,
                    title=f"{full_name} has been inactive",
                    message=(
                        f"Last push was {staleness_days} days ago, beyond the "
                        f"{thresholds.staleness_days}-day staleness threshold."
                    ),
                    dimension=DimensionId.ACTIVITY,
                    evidence=[_source(full_name, "pushed_at")],
                )
            )

    own_signals = [signal for signal in signals if not signal.fork]
    considered_signals = [signal for signal in own_signals if not signal.archived]
    with_push = [signal for signal in considered_signals if signal.staleness_days is not None]
    active_count = sum(1 for signal in with_push if signal.active)
    stale_count = sum(1 for signal in with_push if signal.stale)

    ages = [signal.age_days for signal in signals if signal.age_days is not None]
    staleness = [signal.staleness_days or 0 for signal in with_push]
    max_staleness = max(staleness, default=None)

    buckets = {"<30": 0, "30-90": 0, "90-365": 0, ">365": 0}
    for signal in with_push:
        days = signal.staleness_days or 0
        if days < _RECENT_BUCKET_DAYS:
            buckets["<30"] += 1
        elif days < thresholds.staleness_days:
            buckets["30-90"] += 1
        elif days < _LONG_INACTIVE_DAYS:
            buckets["90-365"] += 1
        else:
            buckets[">365"] += 1

    now_ts = snapshot.collected_at
    metrics = [
        MetricRecord(
            id="portfolio.activity.repos.total",
            label="Repositories total",
            value=len(signals),
            timestamp=now_ts,
            sources=[_source(s.full_name, "name") for s in signals],
        ),
        MetricRecord(
            id="portfolio.activity.repos.active",
            label="Actively maintained repositories",
            value=active_count,
            timestamp=now_ts,
            sources=[_source(s.full_name, "pushed_at") for s in with_push if s.active],
        ),
        MetricRecord(
            id="portfolio.activity.repos.dormant",
            label="Dormant repositories",
            value=stale_count,
            timestamp=now_ts,
            sources=[_source(s.full_name, "pushed_at") for s in with_push if s.stale],
        ),
        MetricRecord(
            id="portfolio.activity.archived_repos",
            label="Archived repositories",
            value=sum(1 for signal in signals if signal.archived),
            timestamp=now_ts,
            sources=[_source(s.full_name, "archived") for s in signals if s.archived],
        ),
        MetricRecord(
            id="portfolio.activity.forked_repos",
            label="Forked repositories",
            value=sum(1 for signal in signals if signal.fork),
            timestamp=now_ts,
            sources=[_source(s.full_name, "fork") for s in signals if s.fork],
        ),
        MetricRecord(
            id="portfolio.activity.median_age_days",
            label="Median repository age (days)",
            value=_median(ages),
            timestamp=now_ts,
            sources=[_source(s.full_name, "created_at") for s in signals],
        ),
        MetricRecord(
            id="portfolio.activity.median_staleness_days",
            label="Median inactivity (days)",
            value=_median(staleness),
            timestamp=now_ts,
            sources=[_source(s.full_name, "pushed_at") for s in with_push],
        ),
        MetricRecord(
            id="portfolio.activity.max_staleness_days",
            label="Longest inactivity (days)",
            value=max_staleness,
            timestamp=now_ts,
            sources=[_source(s.full_name, "pushed_at") for s in with_push],
        ),
        MetricRecord(
            id="portfolio.activity.pushed_recently_30d",
            label="Repositories pushed in the last 30 days",
            value=buckets["<30"],
            timestamp=now_ts,
            sources=[_source(s.full_name, "pushed_at") for s in with_push],
        ),
        MetricRecord(
            id="portfolio.activity.pushed_90d",
            label="Repositories pushed within the staleness window",
            value=buckets["<30"] + buckets["30-90"],
            timestamp=now_ts,
            sources=[_source(s.full_name, "pushed_at") for s in with_push],
        ),
        MetricRecord(
            id="portfolio.activity.pushed_365d",
            label="Repositories pushed within a year",
            value=buckets["<30"] + buckets["30-90"] + buckets["90-365"],
            timestamp=now_ts,
            sources=[_source(s.full_name, "pushed_at") for s in with_push],
        ),
        MetricRecord(
            id="portfolio.activity.pushed_over_365d",
            label="Repositories inactive over a year",
            value=buckets[">365"],
            timestamp=now_ts,
            sources=[_source(s.full_name, "pushed_at") for s in with_push],
        ),
    ]

    if with_push and active_count == 0:
        findings.append(
            Finding(
                id="portfolio.activity.no_recent_activity",
                type="quality_issue",
                severity=FindingSeverity.MEDIUM,
                title="No repository has been pushed recently",
                message=(
                    f"None of the {len(with_push)} owned, non-archived repositories was "
                    f"pushed within the {thresholds.staleness_days}-day staleness window."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=[_source(s.full_name, "pushed_at") for s in with_push],
            )
        )
    if max_staleness is not None and max_staleness > _LONG_INACTIVE_DAYS:
        months = max_staleness // 30
        findings.append(
            Finding(
                id="portfolio.activity.longest_inactive_months",
                type="quality_issue",
                severity=FindingSeverity.LOW,
                title="No repository has been pushed for months",
                message=f"The most recently pushed repository is {months} months old.",
                dimension=DimensionId.ACTIVITY,
                evidence=[_source(s.full_name, "pushed_at") for s in with_push],
            )
        )

    return RepositoryActivity(
        username=snapshot.username,
        signals=signals,
        metrics=metrics,
        findings=findings,
    )
