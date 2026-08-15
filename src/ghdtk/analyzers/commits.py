"""Commit history & activity analysis (issue #38).

Activity signals from the collected commit history: frequency (cadence),
consistency (gaps, active days), per-repository breakdown, and timing patterns
(weekday / hour of day).

Documented coverage policy (mirrors the issue's acceptance criteria):

- **Coverage limits are explicit.** GitHub's commit *search* API caps results
  around 1000 per query and is not used; commits are collected via
  per-repository author-filtered listing
  (``GET /repos/{owner}/{repo}/commits?author=``), paginated within the
  shared page cap and the collection request budget. The collected history is
  therefore a window, not a complete lifetime history, and every finding that
  depends on it states that window.
- **The coverage window** is the span from the earliest to the latest commit
  author date among the collected, date-bearing commits. Time-based metrics
  (cadence, gaps, active days, weekday/hour patterns) are computed only over
  commits that carry an author date; commits without one are still counted in
  ``commit_activity.total_commits`` but disclosed in the coverage-window
  finding. When no dates are available the time-based metrics report
  ``unavailable`` rather than inventing a window.
- **Timing patterns use the author date** as returned by the API (UTC);
  no timezone is assumed beyond what GitHub reports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise

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
from ghdtk.models.raw import Commit, ProfileSnapshot

__all__ = ["CommitActivity", "assess_commit_activity"]

_UNAVAILABLE = "unavailable"
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_HOUR_BUCKETS = [f"{start:02d}-{start + 2:02d}" for start in range(0, 24, 3)]
_DAYS_PER_MONTH = 30.4375


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _commit_date(commit: Commit) -> datetime | None:
    detail = commit.commit
    if detail is None or detail.author is None or detail.author.date is None:
        return None
    return _ensure_utc(detail.author.date)


def _source(identifier: str, field: str) -> SourceReference:
    return SourceReference(
        entity=SourceEntityKind.REPOSITORY,
        identifier=identifier,
        field=field,
    )


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


class CommitActivity(BaseModel):
    """The commit history & activity assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    total_commits: int
    repos_collected: int
    repos_with_commits: int
    coverage_start: datetime | None = None
    coverage_end: datetime | None = None
    span_days: int | None = None
    active_days: int = 0
    cadence_per_month: float | None = None
    median_gap_days: float | None = None
    longest_gap_days: int | None = None
    per_repo_commits: dict[str, int]
    weekday_counts: dict[str, int]
    hour_bucket_counts: dict[str, int]
    metrics: list[MetricRecord]
    findings: list[Finding]


def assess_commit_activity(
    snapshot: ProfileSnapshot,
    *,
    thresholds: AnalysisThresholds | None = None,
) -> CommitActivity:
    """Assess commit frequency, consistency, gaps and timing patterns."""
    thresholds = thresholds or AnalysisThresholds()
    now_ts = snapshot.collected_at
    commits_by_repo = snapshot.commits or {}

    dated: list[tuple[str, datetime]] = []
    per_repo_total: dict[str, int] = {}
    for full_name, commits in commits_by_repo.items():
        per_repo_total[full_name] = len(commits)
        for commit in commits:
            date = _commit_date(commit)
            if date is not None:
                dated.append((full_name, date))

    total_commits = sum(per_repo_total.values())
    repos_collected = len(commits_by_repo)
    repos_with_commits = sum(1 for count in per_repo_total.values() if count > 0)

    active_dates = sorted({_ensure_utc(date).date() for _, date in dated})
    coverage_start = dated[0][1] if dated else None
    coverage_end = dated[-1][1] if dated else None
    span_days = (active_dates[-1] - active_dates[0]).days + 1 if len(active_dates) >= 2 else None
    active_days = len(active_dates)

    gaps = [(later - earlier).days for earlier, later in pairwise(active_dates)]
    longest_gap_days = max(gaps, default=None)
    median_gap_days = _median(gaps) if gaps else None

    cadence_per_month: float | None = None
    if dated and span_days is not None and span_days >= 1:
        cadence_per_month = len(dated) / (span_days / _DAYS_PER_MONTH)

    weekday_counts = {name: 0 for name in _WEEKDAYS}
    for _, date in dated:
        weekday_counts[_WEEKDAYS[date.weekday()]] += 1
    hour_bucket_counts = {bucket: 0 for bucket in _HOUR_BUCKETS}
    for _, date in dated:
        start = (date.hour // 3) * 3
        hour_bucket_counts[f"{start:02d}-{start + 2:02d}"] += 1

    repo_sources = [_source(name, "commit.author.date") for name in per_repo_total]
    findings: list[Finding] = []

    if dated:
        findings.append(
            Finding(
                id="commit_activity.coverage_window",
                type="informational",
                severity=FindingSeverity.INFO,
                title="Commit metrics cover a documented window",
                message=(
                    f"Collected {total_commits} commits ({len(dated)} with author dates) "
                    f"across {repos_with_commits} repositories over "
                    f"{coverage_start:%Y-%m-%d} to {coverage_end:%Y-%m-%d} "
                    f"({span_days} days). Commit history is collected per repository "
                    "within the request budget and may omit older history."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=repo_sources,
            )
        )
    elif total_commits == 0:
        findings.append(
            Finding(
                id="commit_activity.no_commits",
                type="informational",
                severity=FindingSeverity.INFO,
                title="No commits were collected",
                message=(
                    f"No commits were found across {repos_collected} collected "
                    "repositories; commit-based activity metrics are empty."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=repo_sources,
            )
        )
    else:
        findings.append(
            Finding(
                id="commit_activity.no_dates",
                type="informational",
                severity=FindingSeverity.INFO,
                title="Commit dates are unavailable",
                message=(
                    f"{total_commits} commits were collected but none carried an "
                    "author date; time-based metrics report unavailable."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=repo_sources,
            )
        )

    if longest_gap_days is not None and longest_gap_days >= thresholds.commit_gap_days:
        findings.append(
            Finding(
                id="commit_activity.long_gap",
                type="quality_issue",
                severity=FindingSeverity.LOW,
                title="Long gap in the commit history",
                message=(
                    f"The longest gap between commit dates within the coverage window "
                    f"was {longest_gap_days} days."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=repo_sources,
            )
        )

    if cadence_per_month is not None and cadence_per_month >= thresholds.commit_cadence_per_month:
        findings.append(
            Finding(
                id="commit_activity.consistent_cadence",
                type="standout",
                severity=FindingSeverity.INFO,
                title="Consistent commit cadence",
                message=(
                    f"{cadence_per_month:.1f} commits per month on average over the "
                    f"{span_days}-day coverage window."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=repo_sources,
            )
        )

    if len(per_repo_total) > 1:
        top_name, top_count = max(per_repo_total.items(), key=lambda item: item[1])
        if top_count > 0:
            findings.append(
                Finding(
                    id="commit_activity.top_repo",
                    type="standout",
                    severity=FindingSeverity.INFO,
                    title=f"{top_name} is the most active repository",
                    message=(
                        f"{top_count} of {total_commits} collected commits are in {top_name}."
                    ),
                    dimension=DimensionId.ACTIVITY,
                    evidence=[_source(top_name, "commit.author.date")],
                )
            )

    metrics = [
        MetricRecord(
            id="commit_activity.total_commits",
            label="Total commits collected",
            value=total_commits,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="commit_activity.repos_collected",
            label="Repositories with commit collections",
            value=repos_collected,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="commit_activity.repos_with_commits",
            label="Repositories with commits",
            value=repos_with_commits,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="commit_activity.coverage_start",
            label="Coverage window start",
            value=coverage_start.strftime("%Y-%m-%d") if coverage_start else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="commit_activity.coverage_end",
            label="Coverage window end",
            value=coverage_end.strftime("%Y-%m-%d") if coverage_end else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="commit_activity.span_days",
            label="Coverage span (days)",
            value=span_days if span_days is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="commit_activity.active_days",
            label="Active days (distinct commit dates)",
            value=active_days,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="commit_activity.cadence_per_month",
            label="Average commits per month",
            value=_round(cadence_per_month) if cadence_per_month is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="commit_activity.longest_gap_days",
            label="Longest gap between commits (days)",
            value=longest_gap_days if longest_gap_days is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="commit_activity.median_gap_days",
            label="Median gap between commits (days)",
            value=_round(median_gap_days) if median_gap_days is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
    ]
    for full_name, count in sorted(per_repo_total.items()):
        metrics.append(
            MetricRecord(
                id=f"commit_activity.repo.{full_name}",
                label=f"Commits in {full_name}",
                value=count,
                timestamp=now_ts,
                sources=[_source(full_name, "commit.author.date")],
            )
        )
    for name in _WEEKDAYS:
        metrics.append(
            MetricRecord(
                id=f"commit_activity.weekday.{name}",
                label=f"Commits on {name}",
                value=weekday_counts[name],
                timestamp=now_ts,
                sources=repo_sources,
            )
        )
    for bucket in _HOUR_BUCKETS:
        metrics.append(
            MetricRecord(
                id=f"commit_activity.hour.{bucket}",
                label=f"Commits {bucket}:00",
                value=hour_bucket_counts[bucket],
                timestamp=now_ts,
                sources=repo_sources,
            )
        )

    return CommitActivity(
        username=snapshot.username,
        total_commits=total_commits,
        repos_collected=repos_collected,
        repos_with_commits=repos_with_commits,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        span_days=span_days,
        active_days=active_days,
        cadence_per_month=_round(cadence_per_month) if cadence_per_month is not None else None,
        median_gap_days=_round(median_gap_days) if median_gap_days is not None else None,
        longest_gap_days=longest_gap_days,
        per_repo_commits=per_repo_total,
        weekday_counts=weekday_counts,
        hour_bucket_counts=hour_bucket_counts,
        metrics=metrics,
        findings=findings,
    )


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)
