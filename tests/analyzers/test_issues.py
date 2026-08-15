"""Tests for issue participation analysis (issue #42)."""

from __future__ import annotations

from datetime import UTC, datetime

from ghdtk.analyzers.issues import IssueParticipationAnalysis, assess_issue_participation
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import DimensionId, FindingSeverity, MetricValue
from ghdtk.models.raw import Issue, ProfileSnapshot, Repository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _issue(
    number: int,
    *,
    state: str = "open",
    created_at: str = "2024-01-01T00:00:00+00:00",
    closed_at: str | None = None,
    repository_url: str = "https://api.github.com/repos/octocat/Hello-World",
    comments: int | None = None,
) -> Issue:
    return Issue(
        number=number,
        title=f"Issue {number}",
        state=state,
        created_at=datetime.fromisoformat(created_at),
        closed_at=datetime.fromisoformat(closed_at) if closed_at else None,
        repository_url=repository_url,
        comments=comments,
    )


def _snapshot(issues: list[Issue]) -> ProfileSnapshot:
    return ProfileSnapshot(
        username="octocat",
        collected_at=NOW,
        repositories=[Repository(full_name="octocat/Hello-World")],
        search_issues=issues,
    )


def _metric(result: IssueParticipationAnalysis, metric_id: str) -> MetricValue:
    return next(metric.value for metric in result.metrics if metric.id == metric_id)


def test_participation_patterns() -> None:
    issues = [
        _issue(
            1,
            state="closed",
            created_at="2024-01-01T00:00:00+00:00",
            closed_at="2024-01-10T00:00:00+00:00",
            comments=5,
        ),
        _issue(
            2,
            state="closed",
            created_at="2024-01-15T00:00:00+00:00",
            closed_at="2024-01-20T00:00:00+00:00",
            comments=2,
        ),
        _issue(3, state="open", created_at="2024-02-01T00:00:00+00:00", comments=1),
        _issue(
            4,
            state="closed",
            created_at="2024-06-01T00:00:00+00:00",
            closed_at="2024-06-05T00:00:00+00:00",
            repository_url="https://api.github.com/repos/torvalds/linux",
        ),
        _issue(
            5,
            state="closed",
            created_at="2024-07-01T00:00:00+00:00",
            closed_at="2024-07-02T00:00:00+00:00",
            repository_url="https://api.github.com/repos/torvalds/linux",
            comments=1,
        ),
        _issue(
            6,
            state="closed",
            created_at="2024-07-10T00:00:00+00:00",
            closed_at="2024-07-11T00:00:00+00:00",
            repository_url="https://api.github.com/repos/torvalds/linux",
            comments=1,
        ),
        _issue(
            7,
            state="closed",
            created_at="2024-08-01T00:00:00+00:00",
            closed_at="2024-08-02T00:00:00+00:00",
            repository_url="https://api.github.com/repos/torvalds/linux",
            comments=1,
        ),
        _issue(
            8,
            state="closed",
            created_at="2024-08-10T00:00:00+00:00",
            closed_at="2024-08-11T00:00:00+00:00",
            repository_url="https://api.github.com/repos/torvalds/linux",
            comments=1,
        ),
        _issue(
            9,
            state="closed",
            created_at="2024-09-01T00:00:00+00:00",
            closed_at="2024-09-02T00:00:00+00:00",
            repository_url="https://api.github.com/repos/torvalds/linux",
            comments=1,
        ),
        _issue(
            10,
            state="closed",
            created_at="2024-09-10T00:00:00+00:00",
            closed_at="2024-09-11T00:00:00+00:00",
            repository_url="https://api.github.com/repos/torvalds/linux",
            comments=1,
        ),
        _issue(
            11,
            state="closed",
            created_at="2024-10-01T00:00:00+00:00",
            closed_at="2024-10-02T00:00:00+00:00",
            repository_url="https://api.github.com/repos/torvalds/linux",
            comments=1,
        ),
        _issue(
            12,
            state="closed",
            created_at="2024-10-10T00:00:00+00:00",
            closed_at="2024-10-11T00:00:00+00:00",
            repository_url="https://api.github.com/repos/torvalds/linux",
            comments=1,
        ),
    ]
    result = assess_issue_participation(_snapshot(issues))

    assert result.total_issues == 12
    assert result.open_count == 1
    assert result.closed_count == 11
    assert result.close_rate == 0.92
    assert result.median_close_days == 1.0
    assert result.oldest_open_days == 700
    assert result.total_comments == 16
    assert result.issues_with_comments == 11
    assert result.commented_share == 0.92
    assert result.external_count == 9
    assert result.external_share == 0.75
    assert result.repository_diversity == 2
    assert result.trend_direction == "rising"
    assert result.monthly_opened["2024-01"] == 2
    assert result.monthly_opened["2024-10"] == 2
    assert result.monthly_closed["2024-01"] == 2

    assert _metric(result, "issues.total_issues") == 12
    assert _metric(result, "issues.close_rate") == 0.92
    assert _metric(result, "issues.median_close_days") == 1.0
    assert _metric(result, "issues.external_share") == 0.75
    assert _metric(result, "issues.month_opened.2024-01") == 2
    assert _metric(result, "issues.month_closed.2024-01") == 2

    coverage = next(f for f in result.findings if f.id == "issues.coverage_window")
    assert coverage.dimension is DimensionId.ENGAGEMENT
    assert "via the search API" in coverage.message

    external = next(f for f in result.findings if f.id == "issues.external_engagement")
    assert external.severity is FindingSeverity.INFO

    community = next(f for f in result.findings if f.id == "issues.community_participation")
    assert "community participation" in community.title

    rising = next(f for f in result.findings if f.id == "issues.trend_rising")
    assert rising.dimension is DimensionId.ACTIVITY


def test_no_issues() -> None:
    result = assess_issue_participation(_snapshot([]))

    assert result.total_issues == 0
    assert result.close_rate is None
    assert result.trend_direction is None
    assert _metric(result, "issues.close_rate") == "unavailable"
    finding = next(f for f in result.findings if f.id == "issues.no_issues")
    assert finding.severity is FindingSeverity.INFO
    assert not any(f.id == "issues.coverage_window" for f in result.findings)


def test_trend_insufficient_data() -> None:
    issues = [_issue(1, state="open"), _issue(2, state="open")]
    result = assess_issue_participation(_snapshot(issues))

    assert result.trend_direction is None
    finding = next(f for f in result.findings if f.id == "issues.trend_insufficient")
    assert "at least 4 issues" in finding.message
    assert not any(f.id == "issues.trend_rising" for f in result.findings)
    assert not any(f.id == "issues.trend_slowing" for f in result.findings)


def test_trend_rising_threshold_is_config_driven() -> None:
    issues = [
        _issue(1, state="closed", created_at="2024-01-01T00:00:00+00:00"),
        _issue(2, state="closed", created_at="2024-02-01T00:00:00+00:00"),
        _issue(3, state="closed", created_at="2024-06-01T00:00:00+00:00"),
        _issue(4, state="closed", created_at="2024-06-15T00:00:00+00:00"),
        _issue(5, state="closed", created_at="2024-07-01T00:00:00+00:00"),
        _issue(6, state="closed", created_at="2024-07-15T00:00:00+00:00"),
    ]
    default = assess_issue_participation(_snapshot(issues))
    assert default.trend_direction == "rising"
    assert any(f.id == "issues.trend_rising" for f in default.findings)

    strict = assess_issue_participation(
        _snapshot(issues),
        thresholds=AnalysisThresholds(trend_rising_ratio=5.0),
    )
    assert strict.trend_direction is None
    assert not any(f.id == "issues.trend_rising" for f in strict.findings)


def test_external_share_threshold_is_config_driven() -> None:
    issues = [
        _issue(1, state="open", repository_url="https://api.github.com/repos/torvalds/linux"),
        _issue(2, state="open"),
    ]
    default = assess_issue_participation(_snapshot(issues))
    assert any(f.id == "issues.external_engagement" for f in default.findings)

    strict = assess_issue_participation(
        _snapshot(issues),
        thresholds=AnalysisThresholds(issue_external_share=0.9),
    )
    assert not any(f.id == "issues.external_engagement" for f in strict.findings)


def test_commented_share_threshold_is_config_driven() -> None:
    issues = [
        _issue(1, state="open", comments=3),
        _issue(2, state="open", comments=1),
        _issue(3, state="open"),
        _issue(4, state="open"),
    ]
    default = assess_issue_participation(_snapshot(issues))
    assert any(f.id == "issues.community_participation" for f in default.findings)

    strict = assess_issue_participation(
        _snapshot(issues),
        thresholds=AnalysisThresholds(issue_commented_share=0.9),
    )
    assert not any(f.id == "issues.community_participation" for f in strict.findings)
