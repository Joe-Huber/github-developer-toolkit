"""Issue participation analysis (issue #42).

Signals from the issues opened by the profile across all repositories,
collected with the search API (``author:<username> type:issue`` via
``GET /search/issues``).

Documented coverage policy (mirrors the issue's acceptance criteria):

- **Coverage limits are explicit.** The search API caps results around 1000 per
  query and the collection respects the shared page cap and the request
  budget, so the dataset is a window, not a complete lifetime history. Every
  finding that depends on it states that window and the cap.
- **The coverage window** is the span from the earliest to the latest issue
  creation date among the collected, date-bearing items. Time-based metrics
  (time to close, oldest open) are computed only over the issues that carry
  the dates they need; otherwise they report ``unavailable``.
- **Comment participation** is measured with the issue ``comments`` count
  returned by the search API, which counts discussion comments on the issue.
- **Repository classification** uses the item's ``repository_url``; a
  repository is "external" when it is not one of the profile's own
  repositories in the snapshot. Items that name no repository are counted as
  unknown and disclosed, never guessed.
- **Activity trends are reported only where the data supports them.** A trend
  direction is computed only when the collected issues span at least the
  configured minimum distinct months and count; the distinct activity months
  are then split in half and the issues opened in the more recent months are
  compared against those opened in the earlier months. Otherwise the monthly
  breakdown is still reported but no directional finding is made.
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
from ghdtk.models.raw import Issue, ProfileSnapshot

__all__ = ["IssueParticipationAnalysis", "assess_issue_participation"]

_UNAVAILABLE = "unavailable"


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)


def _issue_repo(issue: Issue) -> str | None:
    url = issue.repository_url
    if url:
        parts = [part for part in url.rstrip("/").split("/") if part]
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
    return None


class IssueParticipationAnalysis(BaseModel):
    """The issue participation assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    total_issues: int
    open_count: int
    closed_count: int
    close_rate: float | None = None
    median_close_days: float | None = None
    oldest_open_days: int | None = None
    total_comments: int = 0
    issues_with_comments: int = 0
    commented_share: float | None = None
    external_count: int = 0
    external_share: float | None = None
    unknown_repo_count: int = 0
    repository_diversity: int = 0
    monthly_opened: dict[str, int] = {}
    monthly_closed: dict[str, int] = {}
    trend_direction: str | None = None
    coverage_start: datetime | None = None
    coverage_end: datetime | None = None
    metrics: list[MetricRecord]
    findings: list[Finding]


def assess_issue_participation(
    snapshot: ProfileSnapshot,
    *,
    thresholds: AnalysisThresholds | None = None,
) -> IssueParticipationAnalysis:
    """Assess issue state, close timing, comments, external reach and trends."""
    thresholds = thresholds or AnalysisThresholds()
    now_ts = _ensure_utc(snapshot.collected_at)
    issues = snapshot.search_issues or []
    owned = {repo.full_name for repo in (snapshot.repositories or []) if repo.full_name}

    total = len(issues)
    open_count = sum(1 for issue in issues if issue.state == "open")
    closed_issues = [issue for issue in issues if issue.state == "closed"]
    closed_count = len(closed_issues)
    close_rate = closed_count / total if total > 0 else None

    close_days = [
        (_ensure_utc(issue.closed_at) - _ensure_utc(issue.created_at)).total_seconds() / 86400
        for issue in closed_issues
        if issue.closed_at is not None and issue.created_at is not None
    ]
    median_close_days = _median(close_days) if close_days else None

    oldest_open = min(
        (
            _ensure_utc(issue.created_at)
            for issue in issues
            if issue.state == "open" and issue.created_at is not None
        ),
        default=None,
    )
    oldest_open_days = (
        (now_ts.date() - oldest_open.date()).days if oldest_open is not None else None
    )

    total_comments = sum(issue.comments for issue in issues if issue.comments is not None)
    issues_with_comments = sum(1 for issue in issues if (issue.comments or 0) > 0)
    commented_share = issues_with_comments / total if total > 0 else None

    per_repo_counts: dict[str, int] = {}
    external_count = 0
    unknown_repo_count = 0
    for issue in issues:
        name = _issue_repo(issue)
        if name is None:
            unknown_repo_count += 1
            continue
        per_repo_counts[name] = per_repo_counts.get(name, 0) + 1
        if name not in owned:
            external_count += 1
    external_share = external_count / total if total > 0 else None
    repository_diversity = len(per_repo_counts)

    monthly_opened: dict[str, int] = {}
    for issue in issues:
        if issue.created_at is not None:
            key = _ensure_utc(issue.created_at).strftime("%Y-%m")
            monthly_opened[key] = monthly_opened.get(key, 0) + 1
    monthly_closed: dict[str, int] = {}
    for issue in closed_issues:
        if issue.closed_at is not None:
            key = _ensure_utc(issue.closed_at).strftime("%Y-%m")
            monthly_closed[key] = monthly_closed.get(key, 0) + 1

    months = sorted(monthly_opened)
    early_months = months[: len(months) // 2]
    recent_months = months[len(months) // 2 :]
    early_total = sum(monthly_opened[month] for month in early_months)
    recent_total = sum(monthly_opened[month] for month in recent_months)

    trend_direction: str | None = None
    trend_computed = (
        total >= thresholds.issue_trend_min_issues
        and len(months) >= thresholds.issue_trend_min_months
    )
    if trend_computed and early_total > 0:
        ratio = recent_total / early_total
        if ratio >= thresholds.trend_rising_ratio:
            trend_direction = "rising"
        elif ratio <= thresholds.trend_slowing_ratio:
            trend_direction = "slowing"

    created = sorted(
        _ensure_utc(issue.created_at) for issue in issues if issue.created_at is not None
    )
    coverage_start = created[0] if created else None
    coverage_end = created[-1] if created else None

    repo_sources = [
        SourceReference(
            entity=SourceEntityKind.REPOSITORY,
            identifier=name,
            field="issue",
        )
        for name in sorted(per_repo_counts)
    ]
    findings: list[Finding] = []

    if total == 0:
        findings.append(
            Finding(
                id="issues.no_issues",
                type="informational",
                severity=FindingSeverity.INFO,
                title="No issues were collected",
                message=(
                    "No issues authored by this profile were found via the search API; "
                    "issue participation metrics are empty."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=repo_sources,
            )
        )
    else:
        window = (
            f"{coverage_start:%Y-%m-%d} to {coverage_end:%Y-%m-%d}"
            if coverage_start is not None and coverage_end is not None
            else "unknown"
        )
        unknown_note = (
            f" {unknown_repo_count} items could not be attributed to a repository."
            if unknown_repo_count
            else ""
        )
        findings.append(
            Finding(
                id="issues.coverage_window",
                type="informational",
                severity=FindingSeverity.INFO,
                title="Issue metrics cover a documented window",
                message=(
                    f"Collected {total} issues ({open_count} open, {closed_count} closed) "
                    f"across {repository_diversity} repositories over {window}. Issues are "
                    "collected via the search API within the request budget and may omit "
                    f"older history.{unknown_note}"
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=repo_sources,
            )
        )

    if (
        total > 0
        and external_share is not None
        and external_share >= thresholds.issue_external_share
        and external_count > 0
    ):
        findings.append(
            Finding(
                id="issues.external_engagement",
                type="standout",
                severity=FindingSeverity.INFO,
                title="Issues opened in external repositories",
                message=(
                    f"{external_count} of {total} collected issues "
                    f"({external_share:.0%}) were opened in repositories outside this "
                    "profile's own portfolio."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=repo_sources,
            )
        )

    if (
        total > 0
        and commented_share is not None
        and commented_share >= thresholds.issue_commented_share
        and issues_with_comments > 0
    ):
        findings.append(
            Finding(
                id="issues.community_participation",
                type="standout",
                severity=FindingSeverity.INFO,
                title="Issues attract community participation",
                message=(
                    f"{issues_with_comments} of {total} collected issues "
                    f"({commented_share:.0%}) received comments, indicating discussion "
                    "and engagement around the issues opened."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=repo_sources,
            )
        )

    if trend_direction == "rising":
        findings.append(
            Finding(
                id="issues.trend_rising",
                type="standout",
                severity=FindingSeverity.INFO,
                title="Issue activity is rising",
                message=(
                    f"The more recent months of activity account for {recent_total} "
                    f"collected issues versus {early_total} in the earlier months."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=repo_sources,
            )
        )
    elif trend_direction == "slowing":
        findings.append(
            Finding(
                id="issues.trend_slowing",
                type="quality_issue",
                severity=FindingSeverity.LOW,
                title="Issue activity is slowing",
                message=(
                    f"The more recent months of activity account for {recent_total} "
                    f"collected issues versus {early_total} in the earlier months."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=repo_sources,
            )
        )
    elif total > 0 and not trend_computed:
        findings.append(
            Finding(
                id="issues.trend_insufficient",
                type="informational",
                severity=FindingSeverity.INFO,
                title="Issue activity trends are not reported",
                message=(
                    f"Activity trends require at least {thresholds.issue_trend_min_issues} "
                    f"issues across {thresholds.issue_trend_min_months} distinct months; "
                    f"collected {total} issues across {len(months)} month(s)."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=repo_sources,
            )
        )

    metrics = [
        MetricRecord(
            id="issues.total_issues",
            label="Total issues collected",
            value=total,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.open_count",
            label="Open issues",
            value=open_count,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.closed_count",
            label="Closed issues",
            value=closed_count,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.close_rate",
            label="Close rate (share of collected issues closed)",
            value=_round(close_rate) if close_rate is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.median_close_days",
            label="Median time to close (days)",
            value=_round(median_close_days) if median_close_days is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.oldest_open_days",
            label="Oldest open issue (days)",
            value=oldest_open_days if oldest_open_days is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.total_comments",
            label="Total comments on issues",
            value=total_comments,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.issues_with_comments",
            label="Issues with comments",
            value=issues_with_comments,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.commented_share",
            label="Share of issues with comments",
            value=_round(commented_share) if commented_share is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.external_count",
            label="Issues opened in external repositories",
            value=external_count,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.external_share",
            label="External repository share",
            value=_round(external_share) if external_share is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.unknown_repo_count",
            label="Issues with unknown repository",
            value=unknown_repo_count,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.repository_diversity",
            label="Distinct repositories with issues",
            value=repository_diversity,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.coverage_start",
            label="Coverage window start",
            value=coverage_start.strftime("%Y-%m-%d") if coverage_start else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="issues.coverage_end",
            label="Coverage window end",
            value=coverage_end.strftime("%Y-%m-%d") if coverage_end else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
    ]
    for full_name, count in sorted(per_repo_counts.items()):
        metrics.append(
            MetricRecord(
                id=f"issues.repo.{full_name}",
                label=f"Issues in {full_name}",
                value=count,
                timestamp=now_ts,
                sources=[
                    SourceReference(
                        entity=SourceEntityKind.REPOSITORY,
                        identifier=full_name,
                        field="issue",
                    )
                ],
            )
        )
    for month in months:
        metrics.append(
            MetricRecord(
                id=f"issues.month_opened.{month}",
                label=f"Issues opened in {month}",
                value=monthly_opened[month],
                timestamp=now_ts,
                sources=repo_sources,
            )
        )
    for month in sorted(monthly_closed):
        metrics.append(
            MetricRecord(
                id=f"issues.month_closed.{month}",
                label=f"Issues closed in {month}",
                value=monthly_closed[month],
                timestamp=now_ts,
                sources=repo_sources,
            )
        )

    return IssueParticipationAnalysis(
        username=snapshot.username,
        total_issues=total,
        open_count=open_count,
        closed_count=closed_count,
        close_rate=_round(close_rate) if close_rate is not None else None,
        median_close_days=_round(median_close_days) if median_close_days is not None else None,
        oldest_open_days=oldest_open_days,
        total_comments=total_comments,
        issues_with_comments=issues_with_comments,
        commented_share=_round(commented_share) if commented_share is not None else None,
        external_count=external_count,
        external_share=_round(external_share) if external_share is not None else None,
        unknown_repo_count=unknown_repo_count,
        repository_diversity=repository_diversity,
        monthly_opened=monthly_opened,
        monthly_closed=monthly_closed,
        trend_direction=trend_direction,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        metrics=metrics,
        findings=findings,
    )
