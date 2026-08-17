"""Tests for pull request collection & collaboration analysis (issue #41)."""

from __future__ import annotations

from datetime import UTC, datetime

from ghdtk.analyzers.pull_requests import PullRequestAnalysis, assess_pull_request_collaboration
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import (
    DimensionId,
    FindingSeverity,
    MetricAvailability,
    MetricValue,
)
from ghdtk.models.raw import ProfileSnapshot, PullRequest, Repository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _pull_request(
    number: int,
    *,
    state: str = "open",
    created_at: str = "2024-01-01T00:00:00+00:00",
    merged: bool = False,
    merged_at: str | None = None,
    repository_url: str = "https://api.github.com/repos/octocat/Hello-World",
    review_comments: int | None = None,
    comments: int | None = None,
) -> PullRequest:
    return PullRequest(
        number=number,
        title=f"PR {number}",
        state=state,
        created_at=datetime.fromisoformat(created_at),
        merged=merged,
        merged_at=datetime.fromisoformat(merged_at) if merged_at else None,
        repository_url=repository_url,
        review_comments=review_comments,
        comments=comments,
    )


def _snapshot(pulls: list[PullRequest]) -> ProfileSnapshot:
    return ProfileSnapshot(
        username="octocat",
        collected_at=NOW,
        repositories=[Repository(full_name="octocat/Hello-World")],
        search_pull_requests=pulls,
    )


def _metric(result: PullRequestAnalysis, metric_id: str) -> MetricValue:
    return next(metric.value for metric in result.metrics if metric.id == metric_id)


def _availability(result: PullRequestAnalysis, metric_id: str) -> MetricAvailability:
    return next(metric.availability for metric in result.metrics if metric.id == metric_id)


def test_solo_developer_without_pull_requests() -> None:
    result = assess_pull_request_collaboration(_snapshot([]))

    assert result.total_pull_requests == 0
    assert result.merge_rate is None
    assert _metric(result, "pull_requests.total_pull_requests") == 0
    assert _metric(result, "pull_requests.merge_rate") is None
    assert _availability(result, "pull_requests.merge_rate") is MetricAvailability.UNAVAILABLE
    finding = next(f for f in result.findings if f.id == "pull_requests.no_pull_requests")
    assert finding.severity is FindingSeverity.INFO
    assert not any(f.id == "pull_requests.coverage_window" for f in result.findings)


def test_prolific_contributor_health_metrics() -> None:
    pulls = [
        _pull_request(1, state="open", created_at="2024-01-01T00:00:00+00:00"),
        _pull_request(
            2,
            state="closed",
            created_at="2024-01-05T00:00:00+00:00",
            merged=True,
            merged_at="2024-01-10T00:00:00+00:00",
            review_comments=2,
            comments=3,
        ),
        _pull_request(
            3,
            state="closed",
            created_at="2024-02-01T00:00:00+00:00",
            merged=True,
            merged_at="2024-02-15T00:00:00+00:00",
            review_comments=1,
            repository_url="https://api.github.com/repos/torvalds/linux",
        ),
        _pull_request(
            4,
            state="closed",
            created_at="2024-03-01T00:00:00+00:00",
            merged=False,
            repository_url="https://api.github.com/repos/torvalds/linux",
        ),
        _pull_request(
            5,
            state="closed",
            created_at="2024-04-01T00:00:00+00:00",
            merged=True,
            merged_at="2024-04-10T00:00:00+00:00",
            repository_url="https://api.github.com/repos/torvalds/linux",
            review_comments=5,
        ),
    ]
    result = assess_pull_request_collaboration(_snapshot(pulls))

    assert result.total_pull_requests == 5
    assert result.open_count == 1
    assert result.merged_count == 3
    assert result.closed_count == 4
    assert result.closed_unmerged_count == 1
    assert result.merge_rate == 0.75
    assert result.external_count == 3
    assert result.external_share == 0.6
    assert result.repository_diversity == 2
    assert result.median_time_to_merge_days == 9.0
    assert result.review_comments_total == 8
    assert result.prs_with_review_comments == 3
    assert result.reviewed_share == 0.6
    assert result.prs_with_comments == 1
    assert result.per_repo_counts == {"octocat/Hello-World": 2, "torvalds/linux": 3}

    assert _metric(result, "pull_requests.total_pull_requests") == 5
    assert _metric(result, "pull_requests.merged_count") == 3
    assert _metric(result, "pull_requests.merge_rate") == 0.75
    assert _metric(result, "pull_requests.external_share") == 0.6
    assert _metric(result, "pull_requests.median_time_to_merge_days") == 9.0
    assert _metric(result, "pull_requests.repository_diversity") == 2
    assert _metric(result, "pull_requests.coverage_start") == "2024-01-01"
    assert _metric(result, "pull_requests.coverage_end") == "2024-04-01"

    coverage = next(f for f in result.findings if f.id == "pull_requests.coverage_window")
    assert coverage.dimension is DimensionId.ENGAGEMENT
    assert "via the search API" in coverage.message

    external = next(f for f in result.findings if f.id == "pull_requests.external_engagement")
    assert external.severity is FindingSeverity.INFO

    collaboration = next(f for f in result.findings if f.id == "pull_requests.collaboration")
    assert "review participation" in collaboration.title


def test_external_share_threshold_is_config_driven() -> None:
    pulls = [
        _pull_request(
            1,
            state="closed",
            merged=True,
            merged_at="2024-01-10T00:00:00+00:00",
            repository_url="https://api.github.com/repos/torvalds/linux",
        ),
        _pull_request(
            2,
            state="closed",
            merged=True,
            merged_at="2024-01-10T00:00:00+00:00",
        ),
    ]
    default = assess_pull_request_collaboration(_snapshot(pulls))
    assert any(f.id == "pull_requests.external_engagement" for f in default.findings)

    strict = assess_pull_request_collaboration(
        _snapshot(pulls),
        thresholds=AnalysisThresholds(pr_external_share=0.9),
    )
    assert not any(f.id == "pull_requests.external_engagement" for f in strict.findings)


def test_reviewed_share_threshold_is_config_driven() -> None:
    pulls = [
        _pull_request(1, state="open", review_comments=2),
        _pull_request(2, state="open", review_comments=1),
        _pull_request(3, state="open"),
        _pull_request(4, state="open"),
    ]
    default = assess_pull_request_collaboration(_snapshot(pulls))
    assert any(f.id == "pull_requests.collaboration" for f in default.findings)

    strict = assess_pull_request_collaboration(
        _snapshot(pulls),
        thresholds=AnalysisThresholds(pr_reviewed_share=0.9),
    )
    assert not any(f.id == "pull_requests.collaboration" for f in strict.findings)


def test_time_to_merge_derivable_only_with_dates() -> None:
    pulls = [
        _pull_request(1, state="closed", merged=True),
        _pull_request(2, state="closed", created_at="2024-01-01T00:00:00+00:00", merged_at=None),
    ]
    result = assess_pull_request_collaboration(_snapshot(pulls))

    assert result.merged_count == 1
    assert result.median_time_to_merge_days is None
    assert _metric(result, "pull_requests.median_time_to_merge_days") is None
    assert (
        _availability(result, "pull_requests.median_time_to_merge_days")
        is MetricAvailability.UNAVAILABLE
    )
