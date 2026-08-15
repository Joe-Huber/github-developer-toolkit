"""Pull request collection & collaboration analysis (issue #41).

Health and collaboration signals from the pull requests authored by the
profile across all repositories, collected with the search API
(``author:<username> type:pr`` via ``GET /search/issues``).

Documented coverage policy (mirrors the issue's acceptance criteria):

- **Coverage limits are explicit.** The search API caps results around 1000 per
  query and the collection respects the shared page cap and the request
  budget, so the dataset is a window, not a complete lifetime history. Every
  finding that depends on it states that window and the cap.
- **The coverage window** is the span from the earliest to the latest pull
  request creation date among the collected, date-bearing items. Time-based
  metrics (time to merge) are computed only over pull requests that carry the
  dates they need; otherwise they report ``unavailable``.
- **Collaboration signals use review-comment counts.** Search results expose
  the number of review comments per pull request but not individual reviewers,
  so collaboration is measured through review-comment participation and issue
  comments rather than reviewer identities.
- **Repository classification** uses the item's ``repository_url`` (falling
  back to ``base.repo.full_name``); a repository is "external" when it is not
  one of the profile's own repositories in the snapshot. Items that name no
  repository are counted as unknown and disclosed, never guessed.
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
from ghdtk.models.raw import ProfileSnapshot, PullRequest

__all__ = ["PullRequestAnalysis", "assess_pull_request_collaboration"]

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


def _repo_full_name(pull: PullRequest) -> str | None:
    url = pull.repository_url
    if url:
        parts = [part for part in url.rstrip("/").split("/") if part]
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
    base = pull.base
    if base is not None and base.repo is not None and base.repo.full_name:
        return base.repo.full_name
    return None


def _is_merged(pull: PullRequest) -> bool:
    return bool(pull.merged or pull.merged_at is not None)


class PullRequestAnalysis(BaseModel):
    """The pull request health & collaboration assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    total_pull_requests: int
    open_count: int
    merged_count: int
    closed_count: int
    closed_unmerged_count: int
    merge_rate: float | None = None
    external_count: int = 0
    external_share: float | None = None
    unknown_repo_count: int = 0
    repository_diversity: int = 0
    median_time_to_merge_days: float | None = None
    review_comments_total: int = 0
    prs_with_review_comments: int = 0
    reviewed_share: float | None = None
    comments_total: int = 0
    prs_with_comments: int = 0
    coverage_start: datetime | None = None
    coverage_end: datetime | None = None
    per_repo_counts: dict[str, int] = {}
    metrics: list[MetricRecord]
    findings: list[Finding]


def assess_pull_request_collaboration(
    snapshot: ProfileSnapshot,
    *,
    thresholds: AnalysisThresholds | None = None,
) -> PullRequestAnalysis:
    """Assess pull request health, state mix, merge time and collaboration."""
    thresholds = thresholds or AnalysisThresholds()
    now_ts = snapshot.collected_at
    pulls = snapshot.search_pull_requests or []
    owned = {repo.full_name for repo in (snapshot.repositories or []) if repo.full_name}

    total = len(pulls)
    open_count = sum(1 for pull in pulls if pull.state == "open")
    merged_pulls = [pull for pull in pulls if _is_merged(pull)]
    closed_pulls = [pull for pull in pulls if pull.state == "closed"]
    closed_count = len(closed_pulls)
    closed_unmerged_count = sum(1 for pull in closed_pulls if not _is_merged(pull))
    merged_count = len(merged_pulls)

    resolved = merged_count + closed_unmerged_count
    merge_rate = merged_count / resolved if resolved > 0 else None

    per_repo_counts: dict[str, int] = {}
    external_count = 0
    unknown_repo_count = 0
    for pull in pulls:
        name = _repo_full_name(pull)
        if name is None:
            unknown_repo_count += 1
            continue
        per_repo_counts[name] = per_repo_counts.get(name, 0) + 1
        if name not in owned:
            external_count += 1
    external_share = external_count / total if total > 0 else None
    repository_diversity = len(per_repo_counts)

    merge_days = [
        (_ensure_utc(pull.merged_at) - _ensure_utc(pull.created_at)).total_seconds() / 86400
        for pull in merged_pulls
        if pull.merged_at is not None and pull.created_at is not None
    ]
    median_time_to_merge_days = _median(merge_days) if merge_days else None

    review_comments_total = sum(
        pull.review_comments for pull in pulls if pull.review_comments is not None
    )
    prs_with_review_comments = sum(1 for pull in pulls if (pull.review_comments or 0) > 0)
    reviewed_share = prs_with_review_comments / total if total > 0 else None
    comments_total = sum(pull.comments for pull in pulls if pull.comments is not None)
    prs_with_comments = sum(1 for pull in pulls if (pull.comments or 0) > 0)

    created = sorted(_ensure_utc(pull.created_at) for pull in pulls if pull.created_at is not None)
    coverage_start = created[0] if created else None
    coverage_end = created[-1] if created else None

    repo_sources = [
        SourceReference(
            entity=SourceEntityKind.REPOSITORY,
            identifier=name,
            field="pull_request",
        )
        for name in sorted(per_repo_counts)
    ]
    findings: list[Finding] = []

    if total == 0:
        findings.append(
            Finding(
                id="pull_requests.no_pull_requests",
                type="informational",
                severity=FindingSeverity.INFO,
                title="No pull requests were collected",
                message=(
                    "No pull requests authored by this profile were found via the "
                    "search API; pull request metrics are empty."
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
                id="pull_requests.coverage_window",
                type="informational",
                severity=FindingSeverity.INFO,
                title="Pull request metrics cover a documented window",
                message=(
                    f"Collected {total} pull requests ({merged_count} merged, "
                    f"{open_count} open, {closed_count} closed) across "
                    f"{repository_diversity} repositories over {window}. Pull requests "
                    "are collected via the search API within the request budget and "
                    "may omit older history; review signals reflect review-comment "
                    f"counts only.{unknown_note}"
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=repo_sources,
            )
        )

    if (
        total > 0
        and external_share is not None
        and external_share >= thresholds.pr_external_share
        and external_count > 0
    ):
        findings.append(
            Finding(
                id="pull_requests.external_engagement",
                type="standout",
                severity=FindingSeverity.INFO,
                title="Pull requests target external repositories",
                message=(
                    f"{external_count} of {total} collected pull requests "
                    f"({external_share:.0%}) target repositories outside this "
                    "profile's own portfolio."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=repo_sources,
            )
        )

    if (
        total > 0
        and reviewed_share is not None
        and reviewed_share >= thresholds.pr_reviewed_share
        and prs_with_review_comments > 0
    ):
        findings.append(
            Finding(
                id="pull_requests.collaboration",
                type="standout",
                severity=FindingSeverity.INFO,
                title="Pull requests attract review participation",
                message=(
                    f"{prs_with_review_comments} of {total} collected pull requests "
                    f"({reviewed_share:.0%}) received review comments, indicating "
                    "review collaboration."
                ),
                dimension=DimensionId.ENGAGEMENT,
                evidence=repo_sources,
            )
        )

    metrics = [
        MetricRecord(
            id="pull_requests.total_pull_requests",
            label="Total pull requests collected",
            value=total,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.open_count",
            label="Open pull requests",
            value=open_count,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.merged_count",
            label="Merged pull requests",
            value=merged_count,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.closed_count",
            label="Closed pull requests",
            value=closed_count,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.closed_unmerged_count",
            label="Closed without merge pull requests",
            value=closed_unmerged_count,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.merge_rate",
            label="Merge rate (share of resolved pull requests merged)",
            value=_round(merge_rate) if merge_rate is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.external_count",
            label="Pull requests to external repositories",
            value=external_count,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.external_share",
            label="External repository share",
            value=_round(external_share) if external_share is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.unknown_repo_count",
            label="Pull requests with unknown repository",
            value=unknown_repo_count,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.repository_diversity",
            label="Distinct repositories with pull requests",
            value=repository_diversity,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.median_time_to_merge_days",
            label="Median time to merge (days)",
            value=(
                _round(median_time_to_merge_days)
                if median_time_to_merge_days is not None
                else _UNAVAILABLE
            ),
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.coverage_start",
            label="Coverage window start",
            value=coverage_start.strftime("%Y-%m-%d") if coverage_start else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.coverage_end",
            label="Coverage window end",
            value=coverage_end.strftime("%Y-%m-%d") if coverage_end else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.review_comments_total",
            label="Total review comments",
            value=review_comments_total,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.prs_with_review_comments",
            label="Pull requests with review comments",
            value=prs_with_review_comments,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.reviewed_share",
            label="Share of pull requests with review comments",
            value=_round(reviewed_share) if reviewed_share is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.comments_total",
            label="Total issue comments on pull requests",
            value=comments_total,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="pull_requests.prs_with_comments",
            label="Pull requests with comments",
            value=prs_with_comments,
            timestamp=now_ts,
            sources=repo_sources,
        ),
    ]
    for full_name, count in sorted(per_repo_counts.items()):
        metrics.append(
            MetricRecord(
                id=f"pull_requests.repo.{full_name}",
                label=f"Pull requests in {full_name}",
                value=count,
                timestamp=now_ts,
                sources=[
                    SourceReference(
                        entity=SourceEntityKind.REPOSITORY,
                        identifier=full_name,
                        field="pull_request",
                    )
                ],
            )
        )

    return PullRequestAnalysis(
        username=snapshot.username,
        total_pull_requests=total,
        open_count=open_count,
        merged_count=merged_count,
        closed_count=closed_count,
        closed_unmerged_count=closed_unmerged_count,
        merge_rate=_round(merge_rate) if merge_rate is not None else None,
        external_count=external_count,
        external_share=_round(external_share) if external_share is not None else None,
        unknown_repo_count=unknown_repo_count,
        repository_diversity=repository_diversity,
        median_time_to_merge_days=(
            _round(median_time_to_merge_days) if median_time_to_merge_days is not None else None
        ),
        review_comments_total=review_comments_total,
        prs_with_review_comments=prs_with_review_comments,
        reviewed_share=_round(reviewed_share) if reviewed_share is not None else None,
        comments_total=comments_total,
        prs_with_comments=prs_with_comments,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        per_repo_counts=per_repo_counts,
        metrics=metrics,
        findings=findings,
    )
